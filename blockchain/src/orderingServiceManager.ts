import {
  ManagedBlockchainClient,
  GetNetworkCommand,
  Network,
  NetworkFrameworkAttributes,
  NetworkFabricAttributes
} from '@aws-sdk/client-managedblockchain';
import * as yaml from 'js-yaml';
import * as fs from 'fs/promises';
import * as path from 'path';

/**
 * Ordering service types supported by Hyperledger Fabric
 */
export enum OrderingServiceType {
  SOLO = 'solo',        // Development only - single ordering node
  KAFKA = 'kafka',      // Deprecated - Kafka-based ordering
  RAFT = 'raft'         // Production - Raft consensus protocol
}

/**
 * Interface for Raft consensus configuration
 */
export interface RaftConfig {
  protocol: {
    electionTick: number;
    heartbeatTick: number;
    tickInterval: number;
    maxInflightBlocks: number;
    snapshotIntervalSize: number;
  };
  cluster: {
    nodeCount: number;
    faultTolerance: number;
    azDistribution: Array<{
      zone: string;
      nodes: number;
    }>;
  };
}

/**
 * Interface for ordering service configuration
 */
export interface OrderingServiceConfig {
  type: OrderingServiceType;
  metadata: {
    name: string;
    description: string;
    version: string;  };
  raftConfig: RaftConfig;
  performance: {
    batching: {
      batchTimeout: string;
      maxMessageCount: number;
      absoluteMaxBytes: number;
      preferredMaxBytes: number;
    };
    resources: {
      cpu: { requests: string; limits: string };
      memory: { requests: string; limits: string };
      storage: {
        size: string;
        type: string;
        iops: number;
        throughput: number;
      };
    };
  };
  security: {
    tls: {
      enabled: boolean;
      clientAuthRequired: boolean;
      certRotation: {
        enabled: boolean;
        intervalDays: number;
        gracePeriodDays: number;
      };
    };
    authentication: {
      mutualTLS: {
        enabled: boolean;
        verifyDepth: number;
      };
      clientValidation: {
        checkCRL: boolean;
        checkOCSP: boolean;
      };
    };
    accessControl: {
      adminPolicy: string;
      writerPolicy: string;
      readerPolicy: string;
    };
  };
}

/**
 * Manages ordering service configuration for blockchain network
 */
export class OrderingServiceManager {
  private client: ManagedBlockchainClient;
  private configPath: string;

  constructor(region: string = 'us-east-1') {
    this.client = new ManagedBlockchainClient({ region });
    this.configPath = path.join(__dirname, '..', 'config', 'consensus', 'ordering-service-config.yaml');
  }

  /**
   * Load ordering service configuration
   */
  async loadConfig(): Promise<OrderingServiceConfig> {
    try {
      const configContent = await fs.readFile(this.configPath, 'utf8');
      const config = yaml.load(configContent) as any;
      return config.orderingService as OrderingServiceConfig;
    } catch (error) {
      console.error('Failed to load ordering service configuration:', error);
      throw new Error('Unable to load ordering service configuration');
    }
  }

  /**
   * Validate ordering service type selection
   */
  validateServiceType(type: OrderingServiceType): void {
    if (type === OrderingServiceType.SOLO) {
      console.warn('⚠️  SOLO ordering service is for development only!');
      if (process.env.NODE_ENV === 'production') {
        throw new Error('SOLO ordering service cannot be used in production');
      }
    }

    if (type === OrderingServiceType.KAFKA) {
      console.warn('⚠️  Kafka ordering service is deprecated since Fabric 2.0');
      console.warn('   Consider migrating to Raft consensus');
    }

    if (type === OrderingServiceType.RAFT) {
      console.log('✅ Raft ordering service selected - recommended for production');
    }
  }

  /**
   * Validate Raft configuration
   */
  validateRaftConfig(config: RaftConfig): void {
    // Validate node count
    if (config.cluster.nodeCount % 2 === 0) {
      throw new Error('Raft cluster should have odd number of nodes for optimal fault tolerance');
    }

    if (config.cluster.nodeCount < 3) {
      throw new Error('Raft cluster requires minimum 3 nodes for fault tolerance');
    }

    // Validate fault tolerance
    const expectedFaultTolerance = Math.floor((config.cluster.nodeCount - 1) / 2);
    if (config.cluster.faultTolerance !== expectedFaultTolerance) {
      console.warn(`Fault tolerance should be ${expectedFaultTolerance} for ${config.cluster.nodeCount} nodes`);
    }

    // Validate AZ distribution
    const totalNodes = config.cluster.azDistribution.reduce((sum, az) => sum + az.nodes, 0);
    if (totalNodes !== config.cluster.nodeCount) {
      throw new Error('AZ distribution nodes must equal total node count');
    }

    // Validate protocol settings
    if (config.protocol.electionTick <= config.protocol.heartbeatTick) {
      throw new Error('Election tick must be greater than heartbeat tick');
    }
  }

  /**
   * Generate orderer configuration for AWS Managed Blockchain
   */
  async generateOrdererConfig(networkId: string): Promise<any> {
    const config = await this.loadConfig();

    // Validate configuration
    this.validateServiceType(config.type);
    if (config.type === OrderingServiceType.RAFT) {
      this.validateRaftConfig(config.raftConfig);
    }

    // Get network information
    const network = await this.getNetworkInfo(networkId);

    return {
      OrdererType: config.type.toUpperCase(),
      OrdererOrganizations: await this.getOrdererOrganizations(networkId),      Addresses: await this.getOrdererAddresses(networkId),
      BatchTimeout: config.performance.batching.batchTimeout,
      BatchSize: {
        MaxMessageCount: config.performance.batching.maxMessageCount,
        AbsoluteMaxBytes: config.performance.batching.absoluteMaxBytes,
        PreferredMaxBytes: config.performance.batching.preferredMaxBytes
      },
      EtcdRaft: config.type === OrderingServiceType.RAFT ? {
        Consenters: await this.generateConsenters(networkId, config.raftConfig),
        Options: {
          TickInterval: `${config.raftConfig.protocol.tickInterval}ms`,
          ElectionTick: config.raftConfig.protocol.electionTick,
          HeartbeatTick: config.raftConfig.protocol.heartbeatTick,
          MaxInflightBlocks: config.raftConfig.protocol.maxInflightBlocks,
          SnapshotIntervalSize: config.raftConfig.protocol.snapshotIntervalSize
        }
      } : undefined,
      Policies: {
        Readers: {
          Type: "ImplicitMeta",
          Rule: config.security.accessControl.readerPolicy
        },
        Writers: {
          Type: "ImplicitMeta",
          Rule: config.security.accessControl.writerPolicy
        },
        Admins: {
          Type: "ImplicitMeta",
          Rule: config.security.accessControl.adminPolicy
        }
      }
    };
  }

  /**
   * Get network information from AWS Managed Blockchain
   */
  private async getNetworkInfo(networkId: string): Promise<Network> {
    const command = new GetNetworkCommand({ NetworkId: networkId });
    const response = await this.client.send(command);

    if (!response.Network) {
      throw new Error(`Network ${networkId} not found`);
    }

    return response.Network;
  }

  /**
   * Get orderer organizations for the network
   */
  private async getOrdererOrganizations(networkId: string): Promise<any[]> {
    // In AWS Managed Blockchain, orderer organizations are managed by AWS
    // This returns a placeholder structure
    return [{
      Name: "AWSOrdererOrg",
      ID: "AWSOrdererMSP",
      MSPDir: "crypto-config/ordererOrganizations/aws.com/msp",
      Policies: {
        Readers: {
          Type: "Signature",
          Rule: "OR('AWSOrdererMSP.member')"
        },
        Writers: {
          Type: "Signature",
          Rule: "OR('AWSOrdererMSP.member')"
        },
        Admins: {
          Type: "Signature",
          Rule: "OR('AWSOrdererMSP.admin')"
        }
      }
    }];
  }

  /**
   * Get orderer addresses for the network
   */
  private async getOrdererAddresses(networkId: string): Promise<string[]> {
    const config = await this.loadConfig();
    const addresses: string[] = [];

    // Generate addresses based on AZ distribution
    for (const az of config.raftConfig.cluster.azDistribution) {
      for (let i = 0; i < az.nodes; i++) {
        addresses.push(`orderer${i}.${az.zone}.${networkId}.managedblockchain.com:30001`);
      }
    }

    return addresses;
  }

  /**
   * Generate consenter configuration for Raft
   */
  private async generateConsenters(networkId: string, raftConfig: RaftConfig): Promise<any[]> {
    const consenters: any[] = [];
    let ordererIndex = 0;

    for (const az of raftConfig.cluster.azDistribution) {
      for (let i = 0; i < az.nodes; i++) {
        consenters.push({
          Host: `orderer${ordererIndex}.${az.zone}.${networkId}.managedblockchain.com`,
          Port: 30001,
          ClientTLSCert: `crypto-config/ordererOrganizations/aws.com/orderers/orderer${ordererIndex}/tls/server.crt`,
          ServerTLSCert: `crypto-config/ordererOrganizations/aws.com/orderers/orderer${ordererIndex}/tls/server.crt`
        });
        ordererIndex++;
      }
    }

    return consenters;
  }

  /**
   * Configure ordering service for the network
   */
  async configureOrderingService(networkId: string): Promise<void> {
    try {
      console.log('Loading ordering service configuration...');
      const config = await this.loadConfig();

      console.log(`Selected ordering service type: ${config.type}`);
      this.validateServiceType(config.type);
      if (config.type === OrderingServiceType.RAFT) {
        console.log('Validating Raft configuration...');
        this.validateRaftConfig(config.raftConfig);
        console.log(`✅ Raft cluster with ${config.raftConfig.cluster.nodeCount} nodes configured`);
        console.log(`   Fault tolerance: ${config.raftConfig.cluster.faultTolerance} node failures`);
      }

      console.log('Generating orderer configuration...');
      const ordererConfig = await this.generateOrdererConfig(networkId);

      console.log('Ordering service configuration completed successfully');
      console.log(`Configuration summary:`);
      console.log(`  - Type: ${config.type}`);
      console.log(`  - Batch timeout: ${config.performance.batching.batchTimeout}`);
      console.log(`  - Max message count: ${config.performance.batching.maxMessageCount}`);
      console.log(`  - TLS enabled: ${config.security.tls.enabled}`);

      // Note: In AWS Managed Blockchain, the actual orderer deployment
      // is handled by AWS. This configuration is used for channel creation
      // and chaincode deployment operations.

    } catch (error) {
      console.error('Failed to configure ordering service:', error);
      throw error;
    }
  }
}
