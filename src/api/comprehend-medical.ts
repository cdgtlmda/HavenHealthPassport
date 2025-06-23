import AWS from "aws-sdk";
import { NextApiRequest, NextApiResponse } from "next";

// Configure AWS Comprehend Medical
const comprehendMedical = new AWS.ComprehendMedical({
  region: process.env.AWS_REGION || "us-east-1",
  accessKeyId: process.env.AWS_ACCESS_KEY_ID,
  secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY,
});

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  try {
    const { text } = req.body;

    if (!text) {
      return res.status(400).json({
        error: "Missing required field: text",
      });
    }

    const startTime = Date.now();

    // Run multiple Comprehend Medical operations in parallel
    const [entitiesResult, phiResult, icd10Result, rxNormResult] = await Promise.all([
      // Detect medical entities
      comprehendMedical.detectEntitiesV2({ Text: text }).promise(),

      // Detect PHI (Protected Health Information)
      comprehendMedical.detectPHI({ Text: text }).promise(),

      // Infer ICD-10-CM codes
      comprehendMedical.inferICD10CM({ Text: text }).promise(),

      // Infer RxNorm codes for medications
      comprehendMedical.inferRxNorm({ Text: text }).promise(),
    ]);

    const processingTime = Date.now() - startTime;

    // Process and categorize entities
    const categorizedEntities = {
      medications:
        entitiesResult.Entities?.filter((e) => e.Category === "MEDICATION") || [],
      conditions:
        entitiesResult.Entities?.filter((e) => e.Category === "MEDICAL_CONDITION") ||
        [],
      procedures:
        entitiesResult.Entities?.filter((e) => e.Category === "PROCEDURE") || [],
      anatomy: entitiesResult.Entities?.filter((e) => e.Category === "ANATOMY") || [],
      testResults:
        entitiesResult.Entities?.filter(
          (e) => e.Category === "TEST_TREATMENT_PROCEDURE",
        ) || [],
    };

    // Extract high-confidence entities
    const highConfidenceEntities =
      entitiesResult.Entities?.filter((e) => (e.Score || 0) > 0.8) || [];

    return res.status(200).json({
      success: true,
      originalText: text,
      processingTimeMs: processingTime,

      // Medical entities
      entities: {
        all: entitiesResult.Entities || [],
        categorized: categorizedEntities,
        highConfidence: highConfidenceEntities,
        totalCount: entitiesResult.Entities?.length || 0,
      },

      // PHI detection
      phi: {
        entities: phiResult.Entities || [],
        hasPhiDetected: (phiResult.Entities?.length || 0) > 0,
        phiTypes: [...new Set(phiResult.Entities?.map((e) => e.Category) || [])],
      },

      // ICD-10-CM codes
      icd10: {
        entities: icd10Result.Entities || [],
        codes:
          icd10Result.Entities?.map((e) => ({
            text: e.Text,
            code: e.ICD10CMConcepts?.[0]?.Code || null,
            description: e.ICD10CMConcepts?.[0]?.Description || null,
            score: e.ICD10CMConcepts?.[0]?.Score || null,
          })) || [],
      },

      // RxNorm codes
      rxNorm: {
        entities: rxNormResult.Entities || [],
        medications:
          rxNormResult.Entities?.map((e) => ({
            text: e.Text,
            rxNormId: e.RxNormConcepts?.[0]?.RxCUI || null,
            description: e.RxNormConcepts?.[0]?.Description || null,
            score: e.RxNormConcepts?.[0]?.Score || null,
          })) || [],
      },

      // Summary statistics
      summary: {
        totalEntities: entitiesResult.Entities?.length || 0,
        uniqueCategories: [
          ...new Set(entitiesResult.Entities?.map((e) => e.Category) || []),
        ],
        averageConfidence: entitiesResult.Entities?.length
          ? (
              entitiesResult.Entities.reduce((sum, e) => sum + (e.Score || 0), 0) /
              entitiesResult.Entities.length
            ).toFixed(3)
          : 0,
        hasPhiDetected: (phiResult.Entities?.length || 0) > 0,
        icd10CodesFound: icd10Result.Entities?.length || 0,
        medicationsFound: rxNormResult.Entities?.length || 0,
      },
    });
  } catch (error) {
    console.error("AWS Comprehend Medical error:", error);
    return res.status(500).json({
      error: "Medical entity extraction failed",
      details: error.message,
      service: "AWS Comprehend Medical",
    });
  }
}
