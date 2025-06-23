import AWS from "aws-sdk";
import formidable from "formidable";
import fs from "fs";
import { NextApiRequest, NextApiResponse } from "next";

// Configure AWS
const transcribeService = new AWS.TranscribeService({
  region: process.env.AWS_REGION || "us-east-1",
  accessKeyId: process.env.AWS_ACCESS_KEY_ID,
  secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY,
});

const s3 = new AWS.S3({
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
    const audioFile = Array.isArray(files.audio) ? files.audio[0] : files.audio;

    if (!audioFile) {
      return res.status(400).json({ error: "No audio file provided" });
    }

    const language = Array.isArray(fields.language)
      ? fields.language[0]
      : fields.language || "ar";
    const specialty = Array.isArray(fields.specialty)
      ? fields.specialty[0]
      : fields.specialty || "PRIMARYCARE";
    const type = Array.isArray(fields.type)
      ? fields.type[0]
      : fields.type || "CONVERSATION";

    // Upload audio file to S3 for Transcribe to access
    const bucketName = process.env.AWS_S3_BUCKET || "haven-health-transcribe";
    const fileName = `transcribe-${Date.now()}-${audioFile.originalFilename}`;

    const fileContent = fs.readFileSync(audioFile.filepath);

    const uploadParams = {
      Bucket: bucketName,
      Key: fileName,
      Body: fileContent,
      ContentType: audioFile.mimetype || "audio/wav",
    };

    const uploadResult = await s3.upload(uploadParams).promise();

    // Start transcription job
    const jobName = `medical-transcribe-${Date.now()}`;
    const transcribeParams = {
      MedicalTranscriptionJobName: jobName,
      LanguageCode: language as AWS.TranscribeService.LanguageCode,
      MediaFormat: "wav",
      Media: {
        MediaFileUri: uploadResult.Location,
      },
      OutputBucketName: bucketName,
      OutputKey: `transcripts/${jobName}.json`,
      Specialty: specialty as AWS.TranscribeService.Specialty,
      Type: type as AWS.TranscribeService.Type,
      Settings: {
        ShowSpeakerLabels: true,
        MaxSpeakerLabels: 2,
      },
    };

    const transcribeResult = await transcribeService
      .startMedicalTranscriptionJob(transcribeParams)
      .promise();

    // Poll for completion (simplified for demo - in production use webhooks)
    let jobStatus = "IN_PROGRESS";
    let attempts = 0;
    const maxAttempts = 30; // 5 minutes max wait

    while (jobStatus === "IN_PROGRESS" && attempts < maxAttempts) {
      await new Promise((resolve) => setTimeout(resolve, 10000)); // Wait 10 seconds

      const statusResult = await transcribeService
        .getMedicalTranscriptionJob({
          MedicalTranscriptionJobName: jobName,
        })
        .promise();

      jobStatus =
        statusResult.MedicalTranscriptionJob?.TranscriptionJobStatus || "FAILED";
      attempts++;
    }

    if (jobStatus === "COMPLETED") {
      // Get the transcript from S3
      const transcriptKey = `transcripts/${jobName}.json`;
      const transcriptObject = await s3
        .getObject({
          Bucket: bucketName,
          Key: transcriptKey,
        })
        .promise();

      const transcriptData = JSON.parse(transcriptObject.Body?.toString() || "{}");
      const transcript = transcriptData.results?.transcripts?.[0]?.transcript || "";

      // Clean up uploaded file
      await s3.deleteObject({ Bucket: bucketName, Key: fileName }).promise();

      return res.status(200).json({
        success: true,
        jobName,
        transcript,
        language,
        specialty,
        confidence: transcriptData.results?.transcripts?.[0]?.confidence || null,
        medicalEntities: transcriptData.results?.medical_entities || [],
        rawResults: transcriptData,
      });
    } else {
      // Clean up uploaded file
      await s3.deleteObject({ Bucket: bucketName, Key: fileName }).promise();

      return res.status(500).json({
        error: "Transcription failed or timed out",
        jobStatus,
        jobName,
      });
    }
  } catch (error) {
    console.error("Transcribe Medical error:", error);
    return res.status(500).json({
      error: "Failed to transcribe audio",
      details: error.message,
    });
  }
}
