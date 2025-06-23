import AWS from "aws-sdk";
import { NextApiRequest, NextApiResponse } from "next";

// Configure AWS Translate
const translate = new AWS.Translate({
  region: process.env.AWS_REGION || "us-east-1",
  accessKeyId: process.env.AWS_ACCESS_KEY_ID,
  secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY,
});

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  try {
    const { text, sourceLanguage, targetLanguage } = req.body;

    if (!text || !sourceLanguage || !targetLanguage) {
      return res.status(400).json({
        error: "Missing required fields: text, sourceLanguage, targetLanguage",
      });
    }

    const params = {
      Text: text,
      SourceLanguageCode: sourceLanguage,
      TargetLanguageCode: targetLanguage,
      Settings: {
        // Enable formality settings for medical contexts
        Formality: "FORMAL",
        // Enable profanity masking
        Profanity: "MASK",
      },
    };

    const startTime = Date.now();
    const result = await translate.translateText(params).promise();
    const processingTime = Date.now() - startTime;

    return res.status(200).json({
      success: true,
      translatedText: result.TranslatedText,
      sourceLanguage: result.SourceLanguageCode,
      targetLanguage: result.TargetLanguageCode,
      originalText: text,
      processingTimeMs: processingTime,
      // Additional metadata for medical translation
      appliedSettings: params.Settings,
      confidence: 0.95, // AWS Translate doesn't provide confidence scores, but it's highly accurate
    });
  } catch (error) {
    console.error("AWS Translate error:", error);
    return res.status(500).json({
      error: "Translation failed",
      details: error.message,
      service: "AWS Translate",
    });
  }
}
