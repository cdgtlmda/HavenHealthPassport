import AWS from "aws-sdk";
import formidable from "formidable";
import fs from "fs";
import { NextApiRequest, NextApiResponse } from "next";

// Configure AWS Textract
const textract = new AWS.Textract({
  region: process.env.AWS_REGION || "us-east-1",
  accessKeyId: process.env.AWS_ACCESS_KEY_ID,
  secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY,
});

export const config = {
  api: {
    bodyParser: false,
  },
};

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  try {
    // Parse the uploaded file
    const form = formidable({
      maxFileSize: 10 * 1024 * 1024, // 10MB limit
    });

    const [fields, files] = await form.parse(req);
    const documentFile = Array.isArray(files.document)
      ? files.document[0]
      : files.document;

    if (!documentFile) {
      return res.status(400).json({ error: "No document file provided" });
    }

    // Read the file content
    const fileContent = fs.readFileSync(documentFile.filepath);

    const startTime = Date.now();

    // Use detectDocumentText for basic text extraction
    const textParams = {
      Document: {
        Bytes: fileContent,
      },
    };

    // Use analyzeDocument for more detailed analysis (tables, forms, etc.)
    const analysisParams = {
      Document: {
        Bytes: fileContent,
      },
      FeatureTypes: ["TABLES", "FORMS"] as AWS.Textract.FeatureTypes,
    };

    // Run both operations in parallel
    const [textResult, analysisResult] = await Promise.all([
      textract.detectDocumentText(textParams).promise(),
      textract.analyzeDocument(analysisParams).promise(),
    ]);

    const processingTime = Date.now() - startTime;

    // Extract text content
    const extractedText =
      textResult.Blocks?.filter((block) => block.BlockType === "LINE")
        ?.map((block) => block.Text)
        ?.join("\n") || "";

    // Extract key-value pairs (forms)
    const keyValuePairs =
      analysisResult.Blocks?.filter(
        (block) =>
          block.BlockType === "KEY_VALUE_SET" && block.EntityTypes?.includes("KEY"),
      )?.map((keyBlock) => {
        const valueBlockId = keyBlock.Relationships?.find((rel) => rel.Type === "VALUE")
          ?.Ids?.[0];

        const valueBlock = analysisResult.Blocks?.find(
          (block) => block.Id === valueBlockId,
        );
        const keyText = getTextFromBlock(keyBlock, analysisResult.Blocks || []);
        const valueText = valueBlock
          ? getTextFromBlock(valueBlock, analysisResult.Blocks || [])
          : "";

        return {
          key: keyText,
          value: valueText,
          confidence: {
            key: keyBlock.Confidence || 0,
            value: valueBlock?.Confidence || 0,
          },
        };
      }) || [];

    // Extract tables
    const tables = extractTables(analysisResult.Blocks || []);

    // Medical-specific processing
    const medicalKeywords = extractMedicalKeywords(extractedText);
    const potentialMedications = extractPotentialMedications(extractedText);
    const dates = extractDates(extractedText);

    return res.status(200).json({
      success: true,
      fileName: documentFile.originalFilename,
      fileSize: documentFile.size,
      processingTimeMs: processingTime,

      // Extracted content
      extractedText,
      wordCount: extractedText.split(/\s+/).length,

      // Structured data
      keyValuePairs,
      tables,

      // Medical analysis
      medicalAnalysis: {
        keywords: medicalKeywords,
        potentialMedications,
        dates,
        containsMedicalContent:
          medicalKeywords.length > 0 || potentialMedications.length > 0,
      },

      // Confidence metrics
      confidence: {
        overall: calculateOverallConfidence(textResult.Blocks || []),
        text:
          textResult.Blocks?.reduce((sum, block) => sum + (block.Confidence || 0), 0) /
          (textResult.Blocks?.length || 1),
        forms:
          keyValuePairs.length > 0
            ? keyValuePairs.reduce(
                (sum, pair) => sum + pair.confidence.key + pair.confidence.value,
                0,
              ) /
              (keyValuePairs.length * 2)
            : 0,
      },

      // Raw results for debugging
      rawResults: {
        textBlocks: textResult.Blocks?.length || 0,
        analysisBlocks: analysisResult.Blocks?.length || 0,
        detectedLanguages: textResult.DetectDocumentTextModelVersion,
      },
    });
  } catch (error) {
    console.error("AWS Textract error:", error);
    return res.status(500).json({
      error: "Document text extraction failed",
      details: error.message,
      service: "AWS Textract",
    });
  }
}

// Helper function to get text from a block
function getTextFromBlock(
  block: AWS.Textract.Block,
  allBlocks: AWS.Textract.Block[],
): string {
  if (block.Text) return block.Text;

  const childIds = block.Relationships?.find((rel) => rel.Type === "CHILD")?.Ids || [];
  return childIds
    .map((id) => allBlocks.find((b) => b.Id === id))
    .filter((b) => b?.Text)
    .map((b) => b!.Text)
    .join(" ");
}

// Helper function to extract tables
function extractTables(blocks: AWS.Textract.Block[]) {
  const tables = blocks.filter((block) => block.BlockType === "TABLE");

  return tables.map((table) => {
    const cells =
      table.Relationships?.find((rel) => rel.Type === "CHILD")
        ?.Ids?.map((id) => blocks.find((block) => block.Id === id))
        ?.filter((block) => block?.BlockType === "CELL") || [];

    const rows: string[][] = [];
    cells.forEach((cell) => {
      const rowIndex = (cell.RowIndex || 1) - 1;
      const colIndex = (cell.ColumnIndex || 1) - 1;

      if (!rows[rowIndex]) rows[rowIndex] = [];
      rows[rowIndex][colIndex] = getTextFromBlock(cell, blocks);
    });

    return {
      rows,
      rowCount: table.RowCount || 0,
      columnCount: table.ColumnCount || 0,
      confidence: table.Confidence || 0,
    };
  });
}

// Helper function to calculate overall confidence
function calculateOverallConfidence(blocks: AWS.Textract.Block[]): number {
  const confidences = blocks.map((block) => block.Confidence || 0).filter((c) => c > 0);
  return confidences.length > 0
    ? confidences.reduce((sum, c) => sum + c, 0) / confidences.length
    : 0;
}

// Helper function to extract medical keywords
function extractMedicalKeywords(text: string): string[] {
  const medicalTerms = [
    "medication",
    "prescription",
    "dosage",
    "mg",
    "ml",
    "tablet",
    "capsule",
    "diagnosis",
    "symptom",
    "treatment",
    "therapy",
    "surgery",
    "procedure",
    "blood pressure",
    "heart rate",
    "temperature",
    "weight",
    "height",
    "allergies",
    "medical history",
    "patient",
    "doctor",
    "physician",
    "hospital",
    "clinic",
    "appointment",
    "follow-up",
    "referral",
  ];

  const lowerText = text.toLowerCase();
  return medicalTerms.filter((term) => lowerText.includes(term));
}

// Helper function to extract potential medications
function extractPotentialMedications(text: string): string[] {
  // Simple regex to find words that might be medications
  const medicationPattern = /\b[A-Z][a-z]+(?:in|ol|ide|ine|ate|ium)\b/g;
  const matches = text.match(medicationPattern) || [];
  return [...new Set(matches)]; // Remove duplicates
}

// Helper function to extract dates
function extractDates(text: string): string[] {
  const datePatterns = [
    /\b\d{1,2}\/\d{1,2}\/\d{2,4}\b/g, // MM/DD/YYYY
    /\b\d{1,2}-\d{1,2}-\d{2,4}\b/g, // MM-DD-YYYY
    /\b\w+\s+\d{1,2},?\s+\d{4}\b/g, // Month DD, YYYY
  ];

  const dates: string[] = [];
  datePatterns.forEach((pattern) => {
    const matches = text.match(pattern) || [];
    dates.push(...matches);
  });

  return [...new Set(dates)]; // Remove duplicates
}
