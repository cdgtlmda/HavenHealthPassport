/**
 * Rate Limiting
 * Comprehensive rate limiting for API protection
 */

import { Request, Response, NextFunction } from 'express';
import Redis from 'ioredis';
import { createHash } from 'crypto';

/**
 * Rate limit configuration
 */
export interface RateLimitConfig {
  windowMs: number;           // Time window in milliseconds
  max: number;                // Maximum requests per window
  message?: string;           // Error message
  statusCode?: number;        // HTTP status code
  headers?: boolean;          // Send rate limit headers
  skipSuccessfulRequests?: boolean;  // Don't count successful requests
  skipFailedRequests?: boolean;      // Don't count failed requests
  keyGenerator?: (req: Request) => string;  // Custom key generator
  skip?: (req: Request) => boolean;        // Skip rate limiting
  handler?: (req: Request, res: Response) => void;  // Custom handler
  onLimitReached?: (req: Request, res: Response) => void;  // Limit reached callback
  store?: RateLimitStore;     // Storage backend
}

/**
 * Rate limit store interface
 */
export interface RateLimitStore {
  increment(key: string): Promise<{ count: number; ttl: number }>;
  decrement(key: string): Promise<void>;
  reset(key: string): Promise<void>;
  get(key: string): Promise<number | null>;
}

/**
 * Rate limit info
 */
export interface RateLimitInfo {
  limit: number;
  current: number;
  remaining: number;
  resetTime: Date;
  retryAfter?: number;
}

/**
 * Memory store for rate limiting
 */
export class MemoryStore implements RateLimitStore {
  private store: Map<string, { count: number; resetTime: number }> = new Map();
  private windowMs: number;

  constructor(windowMs: number) {
    this.windowMs = windowMs;
    this.cleanup();
  }

  async increment(key: string): Promise<{ count: number; ttl: number }> {
    const now = Date.now();
    const resetTime = now + this.windowMs;

    const record = this.store.get(key);

    if (record && record.resetTime > now) {
      record.count++;
      return {
        count: record.count,
        ttl: Math.ceil((record.resetTime - now) / 1000)
      };
    } else {
      this.store.set(key, { count: 1, resetTime });
      return {
        count: 1,
        ttl: Math.ceil(this.windowMs / 1000)
      };
    }
  }

  async decrement(key: string): Promise<void> {
    const record = this.store.get(key);
    if (record && record.count > 0) {
      record.count--;
    }
  }

  async reset(key: string): Promise<void> {
    this.store.delete(key);
  }

  async get(key: string): Promise<number | null> {
    const record = this.store.get(key);
    if (record && record.resetTime > Date.now()) {
      return record.count;
    }
    return null;
  }

  private cleanup(): void {
    setInterval(() => {
      const now = Date.now();
      for (const [key, record] of this.store.entries()) {
        if (record.resetTime <= now) {
          this.store.delete(key);
        }
      }
    }, this.windowMs);
  }
}

/**
 * Redis store for rate limiting
 */
export class RedisStore implements RateLimitStore {
  private redis: Redis;
  private windowMs: number;
  private prefix: string;

  constructor(redis: Redis, windowMs: number, prefix: string = 'rate_limit:') {
    this.redis = redis;
    this.windowMs = windowMs;
    this.prefix = prefix;
  }

  async increment(key: string): Promise<{ count: number; ttl: number }> {
    const redisKey = this.prefix + key;
    const ttl = Math.ceil(this.windowMs / 1000);

    const pipeline = this.redis.pipeline();
    pipeline.incr(redisKey);
    pipeline.expire(redisKey, ttl);
    pipeline.ttl(redisKey);

    const results = await pipeline.exec();

    if (!results) {
      throw new Error('Redis pipeline failed');
    }

    const count = results[0][1] as number;
    const actualTtl = results[2][1] as number;

    return { count, ttl: actualTtl > 0 ? actualTtl : ttl };
  }

  async decrement(key: string): Promise<void> {
    const redisKey = this.prefix + key;
    await this.redis.decr(redisKey);
  }

  async reset(key: string): Promise<void> {
    const redisKey = this.prefix + key;
    await this.redis.del(redisKey);
  }

  async get(key: string): Promise<number | null> {
    const redisKey = this.prefix + key;
    const count = await this.redis.get(redisKey);
    return count ? parseInt(count) : null;
  }
}

/**
 * Rate limiter class
 */
export class RateLimiter {
  private config: RateLimitConfig;
  private store: RateLimitStore;

  constructor(config: RateLimitConfig) {
    this.config = {
      windowMs: 60 * 1000,  // 1 minute default
      max: 100,             // 100 requests per window default
      message: 'Too many requests, please try again later.',
      statusCode: 429,
      headers: true,
      skipSuccessfulRequests: false,
      skipFailedRequests: false,
      ...config
    };

    this.store = this.config.store || new MemoryStore(this.config.windowMs);
  }

  /**
   * Express middleware
   */
  middleware() {
    return async (req: Request, res: Response, next: NextFunction) => {
      // Check if should skip
      if (this.config.skip && this.config.skip(req)) {
        return next();
      }

      // Generate key
      const key = this.config.keyGenerator ?
        this.config.keyGenerator(req) :
        this.defaultKeyGenerator(req);

      try {
        // Increment counter
        const { count, ttl } = await this.store.increment(key);

        // Create rate limit info
        const info: RateLimitInfo = {
          limit: this.config.max,
          current: count,
          remaining: Math.max(0, this.config.max - count),
          resetTime: new Date(Date.now() + ttl * 1000)
        };

        // Set headers
        if (this.config.headers) {
          res.setHeader('X-RateLimit-Limit', info.limit.toString());
          res.setHeader('X-RateLimit-Remaining', info.remaining.toString());
          res.setHeader('X-RateLimit-Reset', info.resetTime.toISOString());
        }

        // Check if limit exceeded
        if (count > this.config.max) {
          // Calculate retry after
          info.retryAfter = ttl;

          if (this.config.headers) {
            res.setHeader('Retry-After', info.retryAfter.toString());
          }

          // Call limit reached callback
          if (this.config.onLimitReached) {
            this.config.onLimitReached(req, res);
          }

          // Use custom handler or default
          if (this.config.handler) {
            return this.config.handler(req, res);
          } else {
            return res.status(this.config.statusCode!).json({
              error: this.config.message,
              retryAfter: info.retryAfter
            });
          }
        }

        // Store rate limit info on request
        (req as any).rateLimit = info;

        // Continue to next middleware
        const originalSend = res.send;
        res.send = function(data: any) {
          // Check if should decrement based on response
          if (res.statusCode < 400 && this.config.skipSuccessfulRequests) {
            this.store.decrement(key);
          } else if (res.statusCode >= 400 && this.config.skipFailedRequests) {
            this.store.decrement(key);
          }

          return originalSend.call(this, data);
        }.bind(this);

        next();
      } catch (error) {
        console.error('Rate limiting error:', error);
        next(); // Fail open
      }
    };
  }

  /**
   * Default key generator
   */
  private defaultKeyGenerator(req: Request): string {
    // Use IP address as default key
    const ip = req.ip ||
                req.headers['x-forwarded-for'] ||
                req.headers['x-real-ip'] ||
                req.socket.remoteAddress ||
                'unknown';

    return typeof ip === 'string' ? ip : ip[0];
  }

  /**
   * Reset rate limit for a key
   */
  async reset(key: string): Promise<void> {
    await this.store.reset(key);
  }

  /**
   * Get current count for a key
   */
  async getCount(key: string): Promise<number | null> {
    return this.store.get(key);
  }
}

/**
 * Sliding window rate limiter
 */
export class SlidingWindowRateLimiter extends RateLimiter {
  private redis: Redis;
  private windowMs: number;
  private max: number;
  private prefix: string;

  constructor(config: RateLimitConfig & { redis: Redis }) {
    super(config);
    this.redis = config.redis;
    this.windowMs = config.windowMs;
    this.max = config.max;
    this.prefix = 'sliding_window:';
  }

  middleware() {
    return async (req: Request, res: Response, next: NextFunction) => {
      if (this.config.skip && this.config.skip(req)) {
        return next();
      }

      const key = this.config.keyGenerator ?
        this.config.keyGenerator(req) :
        this.defaultKeyGenerator(req);

      const redisKey = this.prefix + key;
      const now = Date.now();
      const windowStart = now - this.windowMs;

      try {
        // Remove old entries
        await this.redis.zremrangebyscore(redisKey, '-inf', windowStart);

        // Count requests in window
        const count = await this.redis.zcard(redisKey);

        // Create rate limit info
        const info: RateLimitInfo = {
          limit: this.max,
          current: count,
          remaining: Math.max(0, this.max - count),
          resetTime: new Date(now + this.windowMs)
        };

        // Set headers
        if (this.config.headers) {
          res.setHeader('X-RateLimit-Limit', info.limit.toString());
          res.setHeader('X-RateLimit-Remaining', info.remaining.toString());
          res.setHeader('X-RateLimit-Reset', info.resetTime.toISOString());
        }

        // Check if limit exceeded
        if (count >= this.max) {
          // Get oldest request time to calculate retry after
          const oldestRequest = await this.redis.zrange(redisKey, 0, 0, 'WITHSCORES');
          if (oldestRequest.length >= 2) {
            const oldestTime = parseInt(oldestRequest[1]);
            info.retryAfter = Math.ceil((oldestTime + this.windowMs - now) / 1000);

            if (this.config.headers) {
              res.setHeader('Retry-After', info.retryAfter.toString());
            }
          }

          if (this.config.onLimitReached) {
            this.config.onLimitReached(req, res);
          }

          if (this.config.handler) {
            return this.config.handler(req, res);
          } else {
            return res.status(this.config.statusCode!).json({
              error: this.config.message,
              retryAfter: info.retryAfter
            });
          }
        }

        // Add current request
        await this.redis.zadd(redisKey, now, `${now}-${Math.random()}`);
        await this.redis.expire(redisKey, Math.ceil(this.windowMs / 1000));

        (req as any).rateLimit = info;
        next();
      } catch (error) {
        console.error('Sliding window rate limiting error:', error);
        next(); // Fail open
      }
    };
  }

  private defaultKeyGenerator(req: Request): string {
    const ip = req.ip ||
                req.headers['x-forwarded-for'] ||
                req.headers['x-real-ip'] ||
                req.socket.remoteAddress ||
                'unknown';

    return typeof ip === 'string' ? ip : ip[0];
  }
}

/**
 * Token bucket rate limiter
 */
export class TokenBucketRateLimiter {
  private redis: Redis;
  private capacity: number;
  private refillRate: number;
  private prefix: string;

  constructor(config: {
    redis: Redis;
    capacity: number;
    refillRate: number;  // Tokens per second
    prefix?: string;
  }) {
    this.redis = config.redis;
    this.capacity = config.capacity;
    this.refillRate = config.refillRate;
    this.prefix = config.prefix || 'token_bucket:';
  }

  async consume(key: string, tokens: number = 1): Promise<{
    allowed: boolean;
    remaining: number;
    retryAfter?: number;
  }> {
    const redisKey = this.prefix + key;
    const now = Date.now();

    // Lua script for atomic token bucket operations
    const luaScript = `
      local key = KEYS[1]
      local capacity = tonumber(ARGV[1])
      local refill_rate = tonumber(ARGV[2])
      local requested = tonumber(ARGV[3])
      local now = tonumber(ARGV[4])

      local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
      local tokens = tonumber(bucket[1]) or capacity
      local last_refill = tonumber(bucket[2]) or now

      -- Calculate tokens to add based on time elapsed
      local elapsed = math.max(0, now - last_refill) / 1000
      local new_tokens = math.min(capacity, tokens + elapsed * refill_rate)

      if new_tokens >= requested then
        -- Consume tokens
        new_tokens = new_tokens - requested
        redis.call('HMSET', key, 'tokens', new_tokens, 'last_refill', now)
        redis.call('EXPIRE', key, 3600)
        return {1, new_tokens}
      else
        -- Not enough tokens
        local wait_time = (requested - new_tokens) / refill_rate
        return {0, new_tokens, wait_time}
      end
    `;

    const result = await this.redis.eval(
      luaScript,
      1,
      redisKey,
      this.capacity,
      this.refillRate,
      tokens,
      now
    ) as [number, number, number?];

    return {
      allowed: result[0] === 1,
      remaining: Math.floor(result[1]),
      retryAfter: result[2] ? Math.ceil(result[2]) : undefined
    };
  }

  middleware(tokensPerRequest: number = 1) {
    return async (req: Request, res: Response, next: NextFunction) => {
      const key = this.getKey(req);
      const result = await this.consume(key, tokensPerRequest);

      // Set headers
      res.setHeader('X-RateLimit-Limit', this.capacity.toString());
      res.setHeader('X-RateLimit-Remaining', result.remaining.toString());

      if (!result.allowed) {
        if (result.retryAfter) {
          res.setHeader('Retry-After', result.retryAfter.toString());
        }

        return res.status(429).json({
          error: 'Rate limit exceeded',
          retryAfter: result.retryAfter
        });
      }

      next();
    };
  }

  private getKey(req: Request): string {
    const ip = req.ip ||
                req.headers['x-forwarded-for'] ||
                req.headers['x-real-ip'] ||
                req.socket.remoteAddress ||
                'unknown';

    return typeof ip === 'string' ? ip : ip[0];
  }
}

/**
 * Distributed rate limiter for multiple servers
 */
export class DistributedRateLimiter {
  private redis: Redis;
  private nodeId: string;
  private config: RateLimitConfig;

  constructor(config: RateLimitConfig & { redis: Redis; nodeId: string }) {
    this.redis = config.redis;
    this.nodeId = config.nodeId;
    this.config = config;
  }

  middleware() {
    return async (req: Request, res: Response, next: NextFunction) => {
      const key = this.getKey(req);
      const now = Date.now();
      const window = Math.floor(now / this.config.windowMs);
      const redisKey = `dist_rate_limit:${key}:${window}`;

      try {
        // Use Lua script for atomic operations
        const luaScript = `
          local key = KEYS[1]
          local max = tonumber(ARGV[1])
          local ttl = tonumber(ARGV[2])
          local node_id = ARGV[3]

          local current = redis.call('HINCRBY', key, node_id, 1)
          local total = 0

          local counts = redis.call('HVALS', key)
          for i = 1, #counts do
            total = total + tonumber(counts[i])
          end

          redis.call('EXPIRE', key, ttl)

          return {total, current}
        `;

        const [total, nodeCount] = await this.redis.eval(
          luaScript,
          1,
          redisKey,
          this.config.max,
          Math.ceil(this.config.windowMs / 1000),
          this.nodeId
        ) as [number, number];

        const info: RateLimitInfo = {
          limit: this.config.max,
          current: total,
          remaining: Math.max(0, this.config.max - total),
          resetTime: new Date((window + 1) * this.config.windowMs)
        };

        if (this.config.headers) {
          res.setHeader('X-RateLimit-Limit', info.limit.toString());
          res.setHeader('X-RateLimit-Remaining', info.remaining.toString());
          res.setHeader('X-RateLimit-Reset', info.resetTime.toISOString());
          res.setHeader('X-RateLimit-Node', this.nodeId);
        }

        if (total > this.config.max) {
          const retryAfter = Math.ceil((info.resetTime.getTime() - now) / 1000);

          if (this.config.headers) {
            res.setHeader('Retry-After', retryAfter.toString());
          }

          return res.status(this.config.statusCode || 429).json({
            error: this.config.message || 'Rate limit exceeded',
            retryAfter
          });
        }

        (req as any).rateLimit = info;
        next();
      } catch (error) {
        console.error('Distributed rate limiting error:', error);
        next(); // Fail open
      }
    };
  }

  private getKey(req: Request): string {
    if (this.config.keyGenerator) {
      return this.config.keyGenerator(req);
    }

    const ip = req.ip ||
                req.headers['x-forwarded-for'] ||
                req.headers['x-real-ip'] ||
                req.socket.remoteAddress ||
                'unknown';

    return typeof ip === 'string' ? ip : ip[0];
  }
}

/**
 * Rate limit presets
 */
export const RateLimitPresets = {
  // Strict: 10 requests per minute
  strict: {
    windowMs: 60 * 1000,
    max: 10
  },

  // Normal: 100 requests per minute
  normal: {
    windowMs: 60 * 1000,
    max: 100
  },

  // Relaxed: 1000 requests per minute
  relaxed: {
    windowMs: 60 * 1000,
    max: 1000
  },

  // API endpoints
  api: {
    public: { windowMs: 60 * 1000, max: 60 },      // 1 req/sec
    authenticated: { windowMs: 60 * 1000, max: 300 }, // 5 req/sec
    premium: { windowMs: 60 * 1000, max: 600 }     // 10 req/sec
  },

  // Healthcare specific
  healthcare: {
    patientLookup: { windowMs: 60 * 1000, max: 30 },
    prescriptionCreate: { windowMs: 60 * 1000, max: 20 },
    labResultUpload: { windowMs: 60 * 1000, max: 50 },
    emergencyAccess: { windowMs: 60 * 1000, max: 5 }
  },

  // Auth endpoints
  auth: {
    login: { windowMs: 15 * 60 * 1000, max: 5 },    // 5 per 15 min
    register: { windowMs: 60 * 60 * 1000, max: 3 }, // 3 per hour
    passwordReset: { windowMs: 60 * 60 * 1000, max: 3 }
  }
};

// Export convenience functions
export const createRateLimiter = (config: RateLimitConfig) => new RateLimiter(config);
export const createSlidingWindowLimiter = (config: RateLimitConfig & { redis: Redis }) =>
  new SlidingWindowRateLimiter(config);
export const createTokenBucketLimiter = (config: any) => new TokenBucketRateLimiter(config);
export const createDistributedLimiter = (config: any) => new DistributedRateLimiter(config);
