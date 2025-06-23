import { EventEmitter } from 'events';
import * as FileSystem from 'expo-file-system';
import { Image } from 'react-native';
import { Platform } from 'react-native';

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

export class OfflineOCREngine extends EventEmitter {
  private config: OCRConfig;
  private processingQueue: Map<string, Promise<OCRResult>> = new Map();
  private ocrModelPath: string;
  private isModelLoaded = false;
  
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
    
    this.ocrModelPath = `${FileSystem.documentDirectory}ocr_models/`;
    this.initializeOCR();
  }

  /**
   * Initialize OCR engine
   */
  private async initializeOCR(): Promise<void> {
    try {
      // Ensure model directory exists
      const dirInfo = await FileSystem.getInfoAsync(this.ocrModelPath);
      if (!dirInfo.exists) {
        await FileSystem.makeDirectoryAsync(this.ocrModelPath, { intermediates: true });
      }
      
      // Check if models are downloaded
      await this.checkAndDownloadModels();
      
      this.isModelLoaded = true;
      this.emit('ocr-ready');
    } catch (error) {
      console.error('Failed to initialize OCR:', error);
      this.emit('ocr-error', error);
    }
  }

  /**
   * Process image for OCR
   */
  async processImage(imagePath: string, options?: {
    region?: { x: number; y: number; width: number; height: number };
    languages?: string[];
  }): Promise<OCRResult> {
    const processingId = `${imagePath}_${Date.now()}`;
    
    // Check if already processing
    if (this.processingQueue.has(imagePath)) {
      return this.processingQueue.get(imagePath)!;
    }
    
    const processingPromise = this.performOCR(imagePath, options);
    this.processingQueue.set(processingId, processingPromise);
    
    try {
      const result = await processingPromise;
      this.processingQueue.delete(processingId);
      return result;
    } catch (error) {
      this.processingQueue.delete(processingId);
      throw error;
    }
  }

  /**
   * Perform OCR processing
   */
  private async performOCR(
    imagePath: string,
    options?: {
      region?: { x: number; y: number; width: number; height: number };
      languages?: string[];
    }
  ): Promise<OCRResult> {
    const startTime = Date.now();
    
    if (!this.isModelLoaded) {
      throw new Error('OCR models not loaded');
    }
    
    // Preprocess image if enabled
    let processedImagePath = imagePath;
    if (this.config.preprocessImage) {
      processedImagePath = await this.preprocessImage(imagePath);
    }
    
    // Simulate OCR processing (in real implementation, would use ML model)
    // This is a placeholder for actual OCR implementation
    const result = await this.runOCRModel(processedImagePath, options);
    
    // Post-process results
    const processed = this.postProcessResults(result);
    
    const processingTime = Date.now() - startTime;
    
    return {
      ...processed,
      processingTime,
    };
  }

  /**
   * Preprocess image for better OCR results
   */
  private async preprocessImage(imagePath: string): Promise<string> {
    const processedPath = imagePath.replace(/\.[^/.]+$/, '_processed.jpg');
    
    // In a real implementation, this would:
    // 1. Enhance contrast
    // 2. Convert to grayscale
    // 3. Correct rotation/skew
    // 4. Remove noise
    // 5. Adjust brightness
    
    // For now, just copy the image
    await FileSystem.copyAsync({
      from: imagePath,
      to: processedPath,
    });
    
    return processedPath;
  }

  /**
   * Run OCR model (placeholder for actual implementation)
   */
  private async runOCRModel(
    imagePath: string,
    options?: {
      region?: { x: number; y: number; width: number; height: number };
      languages?: string[];
    }
  ): Promise<OCRResult> {
    // In real implementation, this would:
    // 1. Load the image
    // 2. Apply region of interest if specified
    // 3. Run through OCR neural network
    // 4. Extract text blocks and words
    
    // Placeholder implementation
    return {
      text: 'Sample extracted text from image',
      confidence: 0.95,
      blocks: [
        {
          text: 'Sample text block',
          confidence: 0.95,
          boundingBox: { x: 10, y: 10, width: 200, height: 50 },
          words: [
            {
              text: 'Sample',
              confidence: 0.96,
              boundingBox: { x: 10, y: 10, width: 60, height: 50 },
            },
            {
              text: 'text',
              confidence: 0.94,
              boundingBox: { x: 80, y: 10, width: 40, height: 50 },
            },
            {
              text: 'block',
              confidence: 0.95,
              boundingBox: { x: 130, y: 10, width: 50, height: 50 },
            },
          ],
        },
      ],
      language: options?.languages?.[0] || this.config.languages[0],
      processingTime: 0,
    };
  }

  /**
   * Post-process OCR results
   */
  private postProcessResults(result: OCRResult): OCRResult {
    // Filter low confidence results
    const filteredBlocks = result.blocks.filter(
      block => block.confidence >= this.config.minimumConfidence
    );
    
    // Reconstruct text from filtered blocks
    const filteredText = filteredBlocks.map(block => block.text).join('\n');
    
    // Apply text corrections
    const correctedText = this.applyTextCorrections(filteredText);
    
    return {
      ...result,
      text: correctedText,
      blocks: filteredBlocks,
    };
  }

  /**
   * Apply common text corrections
   */
  private applyTextCorrections(text: string): string {
    // Common OCR mistakes
    const corrections: Record<string, string> = {
      'l': 'I', // lowercase L to uppercase I in certain contexts
      '0': 'O', // zero to O in certain contexts
      '5': 'S', // 5 to S in certain contexts
      // Add more corrections based on context
    };
    
    // Apply medical terminology corrections
    const medicalCorrections = this.applyMedicalCorrections(text);
    
    return medicalCorrections;
  }

  /**
   * Apply medical-specific corrections
   */
  private applyMedicalCorrections(text: string): string {
    // Medical terminology patterns
    const medicalPatterns = [
      { pattern: /mg\s*\/\s*dl/gi, replacement: 'mg/dL' },
      { pattern: /mmhg/gi, replacement: 'mmHg' },
      { pattern: /bpm/gi, replacement: 'BPM' },
      // Add more medical patterns
    ];
    
    let corrected = text;
    for (const { pattern, replacement } of medicalPatterns) {
      corrected = corrected.replace(pattern, replacement);
    }
    
    return corrected;
  }

  /**
   * Extract structured data from OCR results
   */
  extractStructuredData(ocrResult: OCRResult, documentType: 'prescription' | 'lab_report' | 'medical_form'): any {
    switch (documentType) {
      case 'prescription':
        return this.extractPrescriptionData(ocrResult);
      
      case 'lab_report':
        return this.extractLabReportData(ocrResult);
      
      case 'medical_form':
        return this.extractMedicalFormData(ocrResult);
      
      default:
        return null;
    }
  }

  /**
   * Extract prescription data
   */
  private extractPrescriptionData(ocrResult: OCRResult): any {
    const text = ocrResult.text;
    
    // Extract medication names, dosages, frequencies
    const medicationPattern = /(\w+)\s+(\d+\s*mg)\s+(.*daily|.*times|.*hours)/gi;
    const medications = [];
    
    let match;
    while ((match = medicationPattern.exec(text)) !== null) {
      medications.push({
        name: match[1],
        dosage: match[2],
        frequency: match[3],
      });
    }
    
    return {
      medications,
      extractedAt: new Date().toISOString(),
      confidence: ocrResult.confidence,
    };
  }

  /**
   * Extract lab report data
   */
  private extractLabReportData(ocrResult: OCRResult): any {
    const text = ocrResult.text;
    
    // Extract test results with values and units
    const testPattern = /([A-Za-z\s]+):\s*(\d+\.?\d*)\s*([A-Za-z\/]+)?/g;
    const results = [];
    
    let match;
    while ((match = testPattern.exec(text)) !== null) {
      results.push({
        test: match[1].trim(),
        value: parseFloat(match[2]),
        unit: match[3] || '',
      });
    }
    
    return {
      results,
      extractedAt: new Date().toISOString(),
      confidence: ocrResult.confidence,
    };
  }

  /**
   * Extract medical form data
   */
  private extractMedicalFormData(ocrResult: OCRResult): any {
    // Extract form fields
    const fields: Record<string, string> = {};
    
    // Look for common form patterns
    const fieldPattern = /([A-Za-z\s]+):\s*([^\n]+)/g;
    let match;
    
    while ((match = fieldPattern.exec(ocrResult.text)) !== null) {
      const fieldName = match[1].trim().toLowerCase().replace(/\s+/g, '_');
      fields[fieldName] = match[2].trim();
    }
    
    return {
      fields,
      extractedAt: new Date().toISOString(),
      confidence: ocrResult.confidence,
    };
  }

  /**
   * Check and download OCR models
   */
  private async checkAndDownloadModels(): Promise<void> {
    // In real implementation, would download models for offline use
    // For now, just create placeholder
    const modelFiles = ['en.traineddata', 'medical_terms.dict'];
    
    for (const file of modelFiles) {
      const filePath = `${this.ocrModelPath}${file}`;
      const fileInfo = await FileSystem.getInfoAsync(filePath);
      
      if (!fileInfo.exists) {
        // In real app, download from server
        // For now, create empty file
        await FileSystem.writeAsStringAsync(filePath, '');
      }
    }
  }

  /**
   * Process batch of images
   */
  async processBatch(imagePaths: string[]): Promise<OCRResult[]> {
    const results = await Promise.all(
      imagePaths.map(path => this.processImage(path))
    );
    
    return results;
  }

  /**
   * Clear OCR cache
   */
  clearCache(): void {
    this.processingQueue.clear();
  }
}

export default OfflineOCREngine;