import AWS from "aws-sdk";
import { NextApiRequest, NextApiResponse } from "next";

// Configure AWS Bedrock Runtime
const bedrockRuntime = new AWS.BedrockRuntime({
  region: process.env.AWS_REGION || "us-east-1",
  accessKeyId: process.env.AWS_ACCESS_KEY_ID,
  secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY,
});

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  try {
    const { text, sourceLanguage, targetLanguage, culturalContext } = req.body;

    if (!text || !sourceLanguage || !targetLanguage) {
      return res.status(400).json({
        error: "Missing required fields: text, sourceLanguage, targetLanguage",
      });
    }

    const startTime = Date.now();

    // Create culturally-aware prompt for Claude 3
    const prompt = createCulturalTranslationPrompt(
      text,
      sourceLanguage,
      targetLanguage,
      culturalContext,
    );

    const requestBody = {
      anthropic_version: "bedrock-2023-05-31",
      max_tokens: 1000,
      messages: [
        {
          role: "user",
          content: prompt,
        },
      ],
      temperature: 0.3, // Lower temperature for more consistent medical translations
      top_p: 0.9,
    };

    const params = {
      modelId: "anthropic.claude-3-sonnet-20240229-v1:0", // Claude 3 Sonnet
      contentType: "application/json",
      accept: "application/json",
      body: JSON.stringify(requestBody),
    };

    const response = await bedrockRuntime.invokeModel(params).promise();
    const responseBody = JSON.parse(response.body.toString());

    const processingTime = Date.now() - startTime;

    // Extract the translation from Claude's response
    const translatedContent = responseBody.content?.[0]?.text || "";

    // Parse Claude's structured response
    const culturalTranslation = parseCulturalResponse(translatedContent);

    return res.status(200).json({
      success: true,
      originalText: text,
      sourceLanguage,
      targetLanguage,
      culturalContext,
      processingTimeMs: processingTime,

      // Main translation result
      culturalTranslation: culturalTranslation.translation,
      standardTranslation: culturalTranslation.standardTranslation,

      // Cultural insights
      culturalInsights: {
        considerations: culturalTranslation.considerations,
        adaptations: culturalTranslation.adaptations,
        medicalAccuracy: culturalTranslation.medicalAccuracy,
        culturalSensitivity: culturalTranslation.culturalSensitivity,
      },

      // Alternative phrasings
      alternatives: culturalTranslation.alternatives || [],

      // Confidence and notes
      confidence: culturalTranslation.confidence || 0.9,
      translatorNotes: culturalTranslation.notes || [],

      // Model information
      model: {
        name: "Claude 3 Sonnet",
        provider: "AWS Bedrock",
        version: "anthropic.claude-3-sonnet-20240229-v1:0",
      },

      // Raw response for debugging
      rawResponse: responseBody,
    });
  } catch (error) {
    console.error("AWS Bedrock error:", error);
    return res.status(500).json({
      error: "Cultural translation failed",
      details: error.message,
      service: "AWS Bedrock (Claude 3)",
    });
  }
}

function createCulturalTranslationPrompt(
  text: string,
  sourceLanguage: string,
  targetLanguage: string,
  culturalContext?: string,
): string {
  return `You are a medical translator specializing in culturally-sensitive healthcare communication for refugee populations.

**Task**: Translate the following medical text with cultural awareness and sensitivity.

**Source Language**: ${sourceLanguage}
**Target Language**: ${targetLanguage}
**Cultural Context**: ${culturalContext || "General multicultural healthcare"}

**Source Text**: "${text}"

**Instructions**:
1. Provide an accurate medical translation that maintains clinical precision
2. Adapt the language for cultural sensitivity and understanding
3. Consider religious, cultural, and social factors that might affect patient comprehension
4. Ensure the translation is appropriate for the target cultural context
5. Maintain medical accuracy while being culturally respectful

**Please provide your response in the following JSON format**:
{
  "standardTranslation": "Direct medical translation",
  "translation": "Culturally-adapted translation",
  "considerations": ["Cultural factor 1", "Cultural factor 2"],
  "adaptations": ["Adaptation made 1", "Adaptation made 2"],
  "medicalAccuracy": "High/Medium/Low - explanation",
  "culturalSensitivity": "High/Medium/Low - explanation",
  "alternatives": ["Alternative phrasing 1", "Alternative phrasing 2"],
  "confidence": 0.95,
  "notes": ["Important note 1", "Important note 2"]
}

Focus on:
- Religious considerations (prayer times, fasting, dietary restrictions)
- Gender-sensitive language and care preferences
- Family involvement in medical decisions
- Traditional medicine integration awareness
- Trauma-informed language for refugee populations
- Clear, simple language that avoids medical jargon when possible`;
}

function parseCulturalResponse(responseText: string) {
  try {
    // Try to extract JSON from the response
    const jsonMatch = responseText.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      return JSON.parse(jsonMatch[0]);
    }

    // Fallback parsing if JSON is not properly formatted
    return {
      translation: responseText,
      standardTranslation: responseText,
      considerations: ["Response parsing needed manual review"],
      adaptations: [],
      medicalAccuracy: "Requires review",
      culturalSensitivity: "Requires review",
      alternatives: [],
      confidence: 0.8,
      notes: ["Response format required manual parsing"],
    };
  } catch (error) {
    console.error("Error parsing cultural response:", error);
    return {
      translation: responseText,
      standardTranslation: responseText,
      considerations: ["Error in response parsing"],
      adaptations: [],
      medicalAccuracy: "Error in parsing",
      culturalSensitivity: "Error in parsing",
      alternatives: [],
      confidence: 0.5,
      notes: ["Error occurred during response parsing"],
    };
  }
}
