import { EventEmitter } from 'events';
import * as FileSystem from 'expo-file-system';
import { Image } from 'react-native';
import { Platform } from 'react-native';
import * as tf from '@tensorflow/tfjs';
import '@tensorflow/tfjs-react-native';

interface OCRResult {
  text: string;
  confidence: number;
  blocks: TextBlock[];
  language?: string;
  processingTime: number;
}

interface TextBlock {
  text: string;
  confidence: number;
  boundingBox: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  words?: Word[];
}

interface Word {
  text: string;
  confidence: number;
  boundingBox: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
}
interface OCRConfig {
  languages: string[];
  preprocessImage: boolean;
  enhanceContrast: boolean;
  correctRotation: boolean;
  minimumConfidence: number;
}

interface OCRModelConfig {
  modelUrl: string;
  weightsUrl: string;
  charsetUrl: string;
}

export class EnhancedOCREngine extends EventEmitter {
  private config: OCRConfig;
  private model: tf.LayersModel | null = null;
  private charset: string[] = [];
  private isInitialized = false;
  private modelConfig: OCRModelConfig = {
    modelUrl: 'https://your-cdn.com/ocr-model/model.json',
    weightsUrl: 'https://your-cdn.com/ocr-model/weights.bin',
    charsetUrl: 'https://your-cdn.com/ocr-model/charset.json',
  };
  
  constructor(config: Partial<OCRConfig> = {}) {
    super();
    this.config = {
      languages: ['en'],
      preprocessImage: true,
      enhanceContrast: true,
      correctRotation: true,
      minimumConfidence: 0.6,
      ...config,
    };
  }
  /**
   * Initialize TensorFlow and load OCR model
   */
  async initialize(): Promise<void> {
    try {
      // Wait for TensorFlow to be ready
      await tf.ready();
      
      // Load the OCR model
      await this.loadModel();
      
      // Load character set
      await this.loadCharset();
      
      this.isInitialized = true;
      this.emit('ocr-ready');
    } catch (error) {
      console.error('Failed to initialize OCR:', error);
      this.emit('ocr-error', error);
    }
  }
  
  /**
   * Load OCR model
   */
  private async loadModel(): Promise<void> {
    try {
      // Check if model exists locally
      const localModelPath = `${FileSystem.documentDirectory}ocr_model/model.json`;
      const modelInfo = await FileSystem.getInfoAsync(localModelPath);
      
      if (modelInfo.exists) {
        // Load from local storage
        this.model = await tf.loadLayersModel(`file://${localModelPath}`);
      } else {
        // Download and cache model
        this.model = await tf.loadLayersModel(this.modelConfig.modelUrl);
        await this.cacheModel();
      }
    } catch (error) {
      console.error('Failed to load OCR model:', error);
      throw error;
    }
  }
  /**
   * Load character set for OCR
   */
  private async loadCharset(): Promise<void> {
    try {
      const response = await fetch(this.modelConfig.charsetUrl);
      this.charset = await response.json();
    } catch (error) {
      // Use default charset
      this.charset = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,!?-\'\"'.split('');
    }
  }
  
  /**
   * Cache model locally
   */
  private async cacheModel(): Promise<void> {
    if (!this.model) return;
    
    const modelPath = `${FileSystem.documentDirectory}ocr_model/`;
    await FileSystem.makeDirectoryAsync(modelPath, { intermediates: true });
    
    // Save model would be implemented here
    // In production, use proper model serialization
  }
  
  /**
   * Process image for OCR
   */
  async processImage(imagePath: string, options?: {
    region?: { x: number; y: number; width: number; height: number };
    languages?: string[];
  }): Promise<OCRResult> {
    const startTime = Date.now();
    
    if (!this.isInitialized || !this.model) {
      throw new Error('OCR engine not initialized');
    }
    
    try {
      // Load and preprocess image
      const tensor = await this.loadAndPreprocessImage(imagePath, options?.region);
      
      // Run OCR model
      const predictions = await this.model.predict(tensor) as tf.Tensor;
      
      // Convert predictions to text
      const result = await this.decodePredictions(predictions);
      
      // Cleanup
      tensor.dispose();
      predictions.dispose();
      
      return {
        ...result,
        processingTime: Date.now() - startTime,
      };
    } catch (error) {
      console.error('OCR processing failed:', error);
      throw error;
    }
  }
  /**
   * Load and preprocess image
   */
  private async loadAndPreprocessImage(
    imagePath: string,
    region?: { x: number; y: number; width: number; height: number }
  ): Promise<tf.Tensor3D> {
    // Load image as tensor
    const imageAssetPath = Image.resolveAssetSource({ uri: imagePath });
    const response = await fetch(imageAssetPath.uri);
    const imageData = await response.blob();
    
    // Convert to tensor
    const imageTensor = await this.blobToTensor(imageData);
    
    // Apply preprocessing
    let processed = imageTensor;
    
    if (this.config.preprocessImage) {
      processed = this.preprocessTensor(processed);
    }
    
    if (region) {
      processed = this.cropRegion(processed, region);
    }
    
    // Normalize and resize for model input
    const normalized = tf.div(processed, 255.0);
    const resized = tf.image.resizeBilinear(normalized as tf.Tensor3D, [64, 256]);
    
    // Cleanup intermediate tensors
    if (processed !== imageTensor) {
      processed.dispose();
    }
    imageTensor.dispose();
    normalized.dispose();
    
    return resized as tf.Tensor3D;
  }
  /**
   * Convert blob to tensor
   */
  private async blobToTensor(blob: Blob): Promise<tf.Tensor> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const img = new Image();
        img.onload = () => {
          const tensor = tf.browser.fromPixels(img);
          resolve(tensor);
        };
        img.onerror = reject;
        img.src = reader.result as string;
      };
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  }
  
  /**
   * Preprocess tensor
   */
  private preprocessTensor(tensor: tf.Tensor): tf.Tensor {
    // Convert to grayscale
    const gray = tf.image.rgbToGrayscale(tensor as tf.Tensor3D);
    
    // Enhance contrast if enabled
    if (this.config.enhanceContrast) {
      // Simple contrast enhancement
      const mean = tf.mean(gray);
      const centered = tf.sub(gray, mean);
      const enhanced = tf.mul(centered, 1.5);
      const shifted = tf.add(enhanced, mean);
      const clipped = tf.clipByValue(shifted, 0, 255);
      
      // Cleanup
      mean.dispose();
      centered.dispose();
      enhanced.dispose();
      shifted.dispose();
      
      return clipped;
    }
    
    return gray;
  }
  /**
   * Crop region from tensor
   */
  private cropRegion(
    tensor: tf.Tensor,
    region: { x: number; y: number; width: number; height: number }
  ): tf.Tensor {
    return tf.slice(
      tensor,
      [region.y, region.x, 0],
      [region.height, region.width, -1]
    );
  }
  
  /**
   * Decode predictions to text
   */
  private async decodePredictions(predictions: tf.Tensor): Promise<OCRResult> {
    const predArray = await predictions.array();
    const decoded = this.ctcDecode(predArray as number[][]);
    
    // Extract text blocks
    const blocks = this.extractTextBlocks(decoded);
    
    // Calculate overall confidence
    const confidence = blocks.reduce((sum, block) => sum + block.confidence, 0) / blocks.length;
    
    return {
      text: blocks.map(b => b.text).join('\n'),
      confidence,
      blocks,
      language: this.config.languages[0],
      processingTime: 0,
    };
  }
  
  /**
   * CTC decode for sequence prediction
   */
  private ctcDecode(predictions: number[][]): Array<{ char: string; confidence: number }> {
    const decoded: Array<{ char: string; confidence: number }> = [];
    let lastChar = -1;
    
    for (const timestep of predictions) {
      const maxIdx = timestep.indexOf(Math.max(...timestep));
      const confidence = timestep[maxIdx];
      
      if (maxIdx !== lastChar && maxIdx < this.charset.length) {
        decoded.push({
          char: this.charset[maxIdx],
          confidence,
        });
      }
      
      lastChar = maxIdx;
    }
    
    return decoded;
  }
  /**
   * Extract text blocks from decoded characters
   */
  private extractTextBlocks(
    decoded: Array<{ char: string; confidence: number }>
  ): TextBlock[] {
    const blocks: TextBlock[] = [];
    let currentBlock = '';
    let blockConfidence = 0;
    let charCount = 0;
    
    for (const { char, confidence } of decoded) {
      if (char === ' ' && currentBlock.length > 0) {
        // End of word/block
        blocks.push({
          text: currentBlock,
          confidence: blockConfidence / charCount,
          boundingBox: { x: 0, y: 0, width: 100, height: 20 }, // Placeholder
        });
        
        currentBlock = '';
        blockConfidence = 0;
        charCount = 0;
      } else {
        currentBlock += char;
        blockConfidence += confidence;
        charCount++;
      }
    }
    
    // Add last block
    if (currentBlock.length > 0) {
      blocks.push({
        text: currentBlock,
        confidence: blockConfidence / charCount,
        boundingBox: { x: 0, y: 0, width: 100, height: 20 }, // Placeholder
      });
    }
    
    return blocks;
  }
}

export default EnhancedOCREngine;