/**
 * Encoding Validation
 * Validates and handles various character encodings
 */

import { TextEncoder, TextDecoder } from 'util';
import iconv from 'iconv-lite';

/**
 * Supported encodings
 */
export const SupportedEncodings = {
  // Unicode encodings
  unicode: ['utf-8', 'utf-16', 'utf-16le', 'utf-16be', 'utf-32', 'utf-32le', 'utf-32be'],

  // ISO encodings
  iso: ['iso-8859-1', 'iso-8859-2', 'iso-8859-3', 'iso-8859-4', 'iso-8859-5',
        'iso-8859-6', 'iso-8859-7', 'iso-8859-8', 'iso-8859-9', 'iso-8859-10',
        'iso-8859-11', 'iso-8859-13', 'iso-8859-14', 'iso-8859-15', 'iso-8859-16'],

  // Windows encodings
  windows: ['windows-1250', 'windows-1251', 'windows-1252', 'windows-1253',
            'windows-1254', 'windows-1255', 'windows-1256', 'windows-1257',
            'windows-1258'],

  // Other common encodings
  other: ['ascii', 'base64', 'hex', 'binary', 'latin1']
};

/**
 * Encoding validation options
 */
export interface EncodingValidationOptions {
  allowedEncodings?: string[];
  targetEncoding?: string;
  detectEncoding?: boolean;
  handleBOM?: boolean;
  replaceInvalid?: boolean;
  strict?: boolean;
}

/**
 * Encoding validator class
 */
export class EncodingValidator {
  /**
   * Detect encoding of a buffer
   */
  static detectEncoding(buffer: Buffer): string | null {
    // Check for BOM (Byte Order Mark)
    if (buffer.length >= 3) {
      // UTF-8 BOM
      if (buffer[0] === 0xEF && buffer[1] === 0xBB && buffer[2] === 0xBF) {
        return 'utf-8';
      }
      // UTF-16 LE BOM
      if (buffer[0] === 0xFF && buffer[1] === 0xFE) {
        return 'utf-16le';
      }
      // UTF-16 BE BOM
      if (buffer[0] === 0xFE && buffer[1] === 0xFF) {
        return 'utf-16be';
      }
    }

    // Check for UTF-32 BOM
    if (buffer.length >= 4) {
      // UTF-32 LE BOM
      if (buffer[0] === 0xFF && buffer[1] === 0xFE &&
          buffer[2] === 0x00 && buffer[3] === 0x00) {
        return 'utf-32le';
      }
      // UTF-32 BE BOM
      if (buffer[0] === 0x00 && buffer[1] === 0x00 &&
          buffer[2] === 0xFE && buffer[3] === 0xFF) {
        return 'utf-32be';
      }
    }

    // Try to detect UTF-8
    if (this.isValidUTF8(buffer)) {
      return 'utf-8';
    }

    // Try to detect ASCII
    if (this.isASCII(buffer)) {
      return 'ascii';
    }

    // Default to ISO-8859-1 if can't detect
    return 'iso-8859-1';
  }

  /**
   * Check if buffer is valid UTF-8
   */
  static isValidUTF8(buffer: Buffer): boolean {
    try {
      const decoder = new TextDecoder('utf-8', { fatal: true });
      decoder.decode(buffer);
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Check if buffer contains only ASCII characters
   */
  static isASCII(buffer: Buffer): boolean {
    for (let i = 0; i < buffer.length; i++) {
      if (buffer[i] > 127) {
        return false;
      }
    }
    return true;
  }

  /**
   * Validate encoding
   */
  static validate(
    input: string | Buffer,
    encoding: string,
    options: EncodingValidationOptions = {}
  ): { valid: boolean; error?: string; detectedEncoding?: string } {
    // Check if encoding is allowed
    if (options.allowedEncodings && !options.allowedEncodings.includes(encoding)) {
      return {
        valid: false,
        error: `Encoding '${encoding}' is not allowed`
      };
    }

    const buffer = Buffer.isBuffer(input) ? input : Buffer.from(input);

    // Detect encoding if requested
    if (options.detectEncoding) {
      const detected = this.detectEncoding(buffer);
      if (detected && detected !== encoding) {
        return {
          valid: false,
          error: `Detected encoding '${detected}' does not match specified '${encoding}'`,
          detectedEncoding: detected
        };
      }
    }

    // Validate the encoding
    try {
      if (iconv.encodingExists(encoding)) {
        const decoded = iconv.decode(buffer, encoding);
        const reencoded = iconv.encode(decoded, encoding);

        // In strict mode, check if re-encoding matches original
        if (options.strict && !buffer.equals(reencoded)) {
          return {
            valid: false,
            error: 'Encoding validation failed: data loss detected'
          };
        }

        return { valid: true };
      } else {
        return {
          valid: false,
          error: `Unknown encoding: ${encoding}`
        };
      }
    } catch (error) {
      return {
        valid: false,
        error: `Invalid ${encoding} encoding: ${error.message}`
      };
    }
  }

  /**
   * Convert between encodings
   */
  static convert(
    input: string | Buffer,
    fromEncoding: string,
    toEncoding: string,
    options: EncodingValidationOptions = {}
  ): { success: boolean; output?: Buffer; error?: string } {
    try {
      const buffer = Buffer.isBuffer(input) ? input : Buffer.from(input, fromEncoding as BufferEncoding);

      // Handle BOM if requested
      let processedBuffer = buffer;
      if (options.handleBOM) {
        processedBuffer = this.removeBOM(buffer);
      }

      // Convert encoding
      const decoded = iconv.decode(processedBuffer, fromEncoding);
      const encoded = iconv.encode(decoded, toEncoding);

      return {
        success: true,
        output: encoded
      };
    } catch (error) {
      return {
        success: false,
        error: `Encoding conversion failed: ${error.message}`
      };
    }
  }

  /**
   * Remove BOM from buffer
   */
  static removeBOM(buffer: Buffer): Buffer {
    // UTF-8 BOM
    if (buffer.length >= 3 &&
        buffer[0] === 0xEF && buffer[1] === 0xBB && buffer[2] === 0xBF) {
      return buffer.slice(3);
    }

    // UTF-16 LE BOM
    if (buffer.length >= 2 &&
        buffer[0] === 0xFF && buffer[1] === 0xFE) {
      return buffer.slice(2);
    }

    // UTF-16 BE BOM
    if (buffer.length >= 2 &&
        buffer[0] === 0xFE && buffer[1] === 0xFF) {
      return buffer.slice(2);
    }

    // UTF-32 BOM
    if (buffer.length >= 4) {
      if ((buffer[0] === 0xFF && buffer[1] === 0xFE &&
           buffer[2] === 0x00 && buffer[3] === 0x00) ||
          (buffer[0] === 0x00 && buffer[1] === 0x00 &&
           buffer[2] === 0xFE && buffer[3] === 0xFF)) {
        return buffer.slice(4);
      }
    }

    return buffer;
  }

  /**
   * Add BOM to buffer
   */
  static addBOM(buffer: Buffer, encoding: string): Buffer {
    const bomMap: Record<string, Buffer> = {
      'utf-8': Buffer.from([0xEF, 0xBB, 0xBF]),
      'utf-16le': Buffer.from([0xFF, 0xFE]),
      'utf-16be': Buffer.from([0xFE, 0xFF]),
      'utf-32le': Buffer.from([0xFF, 0xFE, 0x00, 0x00]),
      'utf-32be': Buffer.from([0x00, 0x00, 0xFE, 0xFF])
    };

    const bom = bomMap[encoding.toLowerCase()];
    if (bom) {
      return Buffer.concat([bom, buffer]);
    }

    return buffer;
  }

  /**
   * Sanitize string for specific encoding
   */
  static sanitizeForEncoding(
    input: string,
    targetEncoding: string,
    options: EncodingValidationOptions = {}
  ): string {
    try {
      // Encode to target encoding and back to detect unsupported characters
      const encoded = iconv.encode(input, targetEncoding);
      let decoded = iconv.decode(encoded, targetEncoding);

      // If characters were lost, handle based on options
      if (input !== decoded && options.replaceInvalid) {
        // Replace invalid characters with a placeholder
        const placeholder = '?';
        const inputChars = [...input];
        const decodedChars = [...decoded];

        let result = '';
        for (let i = 0; i < inputChars.length; i++) {
          if (i < decodedChars.length && inputChars[i] === decodedChars[i]) {
            result += inputChars[i];
          } else {
            result += placeholder;
          }
        }

        return result;
      }

      return decoded;
    } catch {
      return options.replaceInvalid ? input.replace(/[^\x00-\x7F]/g, '?') : input;
    }
  }

  /**
   * Check if string contains only characters valid in encoding
   */
  static hasValidCharacters(input: string, encoding: string): boolean {
    try {
      const encoded = iconv.encode(input, encoding);
      const decoded = iconv.decode(encoded, encoding);
      return input === decoded;
    } catch {
      return false;
    }
  }

  /**
   * Get list of invalid characters for encoding
   */
  static getInvalidCharacters(input: string, encoding: string): string[] {
    const invalid: string[] = [];

    for (const char of input) {
      if (!this.hasValidCharacters(char, encoding)) {
        if (!invalid.includes(char)) {
          invalid.push(char);
        }
      }
    }

    return invalid;
  }

  /**
   * Normalize line endings
   */
  static normalizeLineEndings(input: string, style: 'unix' | 'windows' | 'mac' = 'unix'): string {
    // First normalize all to \n
    let normalized = input.replace(/\r\n/g, '\n').replace(/\r/g, '\n');

    // Then convert to desired style
    switch (style) {
      case 'windows':
        return normalized.replace(/\n/g, '\r\n');
      case 'mac':
        return normalized.replace(/\n/g, '\r');
      case 'unix':
      default:
        return normalized;
    }
  }

  /**
   * Check for mixed line endings
   */
  static hasMixedLineEndings(input: string): boolean {
    const hasUnix = input.includes('\n') && !input.includes('\r\n');
    const hasWindows = input.includes('\r\n');
    const hasMac = input.includes('\r') && !input.includes('\r\n');

    return [hasUnix, hasWindows, hasMac].filter(Boolean).length > 1;
  }

  /**
   * Escape special characters for HTML
   */
  static escapeHTML(input: string): string {
    const escapeMap: Record<string, string> = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;',
      '/': '&#x2F;'
    };

    return input.replace(/[&<>"'\/]/g, char => escapeMap[char]);
  }

  /**
   * Escape special characters for XML
   */
  static escapeXML(input: string): string {
    return input
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&apos;');
  }

  /**
   * Escape special characters for JSON
   */
  static escapeJSON(input: string): string {
    return JSON.stringify(input).slice(1, -1);
  }

  /**
   * Escape special characters for CSV
   */
  static escapeCSV(input: string): string {
    if (input.includes(',') || input.includes('"') || input.includes('\n')) {
      return '"' + input.replace(/"/g, '""') + '"';
    }
    return input;
  }

  /**
   * Escape special characters for SQL (use parameterized queries instead!)
   */
  static escapeSQL(input: string): string {
    return input
      .replace(/\\/g, '\\\\')
      .replace(/'/g, "\\'")
      .replace(/"/g, '\\"')
      .replace(/\x00/g, '\\0')
      .replace(/\n/g, '\\n')
      .replace(/\r/g, '\\r')
      .replace(/\x1a/g, '\\Z');
  }

  /**
   * Validate and normalize Unicode
   */
  static normalizeUnicode(input: string, form: 'NFC' | 'NFD' | 'NFKC' | 'NFKD' = 'NFC'): string {
    return input.normalize(form);
  }

  /**
   * Check for homoglyphs (visually similar characters)
   */
  static hasHomoglyphs(input: string): boolean {
    // Common homoglyphs
    const homoglyphPatterns = [
      /[АВЕКМНОРСТХаеорсух]/u, // Cyrillic letters that look like Latin
      /[Αα Ββ Εε Ζζ Ηη Ιι Κκ Μμ Νν Οο Ρρ Ττ Χχ]/u, // Greek letters
      /[０-９]/u, // Full-width digits
      /[Ａ-Ｚａ-ｚ]/u // Full-width Latin letters
    ];

    return homoglyphPatterns.some(pattern => pattern.test(input));
  }

  /**
   * Remove zero-width characters
   */
  static removeZeroWidth(input: string): string {
    // Zero-width characters
    const zeroWidthChars = [
      '\u200B', // Zero-width space
      '\u200C', // Zero-width non-joiner
      '\u200D', // Zero-width joiner
      '\uFEFF', // Zero-width non-breaking space
      '\u2060', // Word joiner
      '\u180E'  // Mongolian vowel separator
    ];

    let result = input;
    for (const char of zeroWidthChars) {
      result = result.replace(new RegExp(char, 'g'), '');
    }

    return result;
  }

  /**
   * Check for invisible characters
   */
  static hasInvisibleCharacters(input: string): boolean {
    // Invisible and control characters
    const invisiblePattern = /[\x00-\x1F\x7F-\x9F\u200B-\u200F\u2028-\u202F\u205F-\u206F\uFEFF]/;
    return invisiblePattern.test(input);
  }

  /**
   * Validate character range
   */
  static isInCharacterRange(input: string, ranges: Array<[number, number]>): boolean {
    for (const char of input) {
      const code = char.charCodeAt(0);
      const inRange = ranges.some(([min, max]) => code >= min && code <= max);
      if (!inRange) {
        return false;
      }
    }
    return true;
  }

  /**
   * Get character statistics
   */
  static getCharacterStats(input: string): {
    ascii: number;
    latin1: number;
    unicode: number;
    control: number;
    whitespace: number;
    digits: number;
    letters: number;
    punctuation: number;
    other: number;
  } {
    const stats = {
      ascii: 0,
      latin1: 0,
      unicode: 0,
      control: 0,
      whitespace: 0,
      digits: 0,
      letters: 0,
      punctuation: 0,
      other: 0
    };

    for (const char of input) {
      const code = char.charCodeAt(0);

      // Character type
      if (code <= 127) stats.ascii++;
      else if (code <= 255) stats.latin1++;
      else stats.unicode++;

      // Character category
      if (code < 32 || code === 127) stats.control++;
      else if (/\s/.test(char)) stats.whitespace++;
      else if (/\d/.test(char)) stats.digits++;
      else if (/[a-zA-Z]/.test(char)) stats.letters++;
      else if (/[!"#$%&'()*+,\-./:;<=>?@[\\\]^_`{|}~]/.test(char)) stats.punctuation++;
      else stats.other++;
    }

    return stats;
  }
}

/**
 * Encoding utility functions
 */
export class EncodingUtils {
  /**
   * Convert string to base64
   */
  static toBase64(input: string, encoding: BufferEncoding = 'utf8'): string {
    return Buffer.from(input, encoding).toString('base64');
  }

  /**
   * Convert base64 to string
   */
  static fromBase64(input: string, encoding: BufferEncoding = 'utf8'): string {
    return Buffer.from(input, 'base64').toString(encoding);
  }

  /**
   * Convert string to hex
   */
  static toHex(input: string, encoding: BufferEncoding = 'utf8'): string {
    return Buffer.from(input, encoding).toString('hex');
  }

  /**
   * Convert hex to string
   */
  static fromHex(input: string, encoding: BufferEncoding = 'utf8'): string {
    return Buffer.from(input, 'hex').toString(encoding);
  }

  /**
   * URL encode
   */
  static urlEncode(input: string): string {
    return encodeURIComponent(input);
  }

  /**
   * URL decode
   */
  static urlDecode(input: string): string {
    return decodeURIComponent(input);
  }

  /**
   * HTML entity encode
   */
  static htmlEncode(input: string): string {
    return input
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#x27;')
      .replace(/\//g, '&#x2F;');
  }

  /**
   * HTML entity decode
   */
  static htmlDecode(input: string): string {
    const textarea = document.createElement('textarea');
    textarea.innerHTML = input;
    return textarea.value;
  }
}

// Export convenience functions
export const detectEncoding = EncodingValidator.detectEncoding.bind(EncodingValidator);
export const validateEncoding = EncodingValidator.validate.bind(EncodingValidator);
export const convertEncoding = EncodingValidator.convert.bind(EncodingValidator);
export const sanitizeForEncoding = EncodingValidator.sanitizeForEncoding.bind(EncodingValidator);
export const normalizeLineEndings = EncodingValidator.normalizeLineEndings.bind(EncodingValidator);
export const escapeHTML = EncodingValidator.escapeHTML.bind(EncodingValidator);
export const escapeXML = EncodingValidator.escapeXML.bind(EncodingValidator);
export const escapeJSON = EncodingValidator.escapeJSON.bind(EncodingValidator);
export const escapeCSV = EncodingValidator.escapeCSV.bind(EncodingValidator);
export const normalizeUnicode = EncodingValidator.normalizeUnicode.bind(EncodingValidator);
export const removeZeroWidth = EncodingValidator.removeZeroWidth.bind(EncodingValidator);
