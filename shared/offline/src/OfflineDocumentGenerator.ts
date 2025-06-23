import { EventEmitter } from 'events';
import * as FileSystem from 'expo-file-system';
import AsyncStorage from '@react-native-async-storage/async-storage';

interface DocumentTemplate {
  id: string;
  name: string;
  category: 'medical' | 'administrative' | 'legal' | 'educational';
  description: string;
  fields: TemplateField[];
  layout: TemplateLayout;
  styles: TemplateStyles;
  metadata: {
    version: string;
    createdAt: number;
    updatedAt: number;
    author: string;
    tags: string[];
  };
}

interface TemplateField {
  id: string;
  name: string;
  type: 'text' | 'number' | 'date' | 'select' | 'checkbox' | 'signature' | 'image';
  label: string;
  required: boolean;
  defaultValue?: any;
  validation?: {
    pattern?: string;
    min?: number;
    max?: number;
    options?: string[];
  };
  placeholder?: string;
  helpText?: string;
}

interface TemplateLayout {
  sections: Array<{
    id: string;
    title?: string;
    fields: string[]; // field IDs
    columns?: number;
  }>;
  header?: {
    logo?: boolean;
    title: string;
    subtitle?: string;
  };
  footer?: {
    text?: string;
    pageNumbers?: boolean;
  };
}

interface TemplateStyles {
  theme: 'default' | 'medical' | 'formal' | 'simple';
  colors: {
    primary: string;
    secondary: string;
    text: string;
    background: string;
  };
  fonts: {
    heading: string;
    body: string;
  };
  spacing: 'compact' | 'normal' | 'relaxed';
}

interface GeneratedDocument {
  id: string;
  templateId: string;
  data: Record<string, any>;
  format: 'pdf' | 'html' | 'docx';
  generatedAt: number;
  filePath: string;
}

export class OfflineDocumentGenerator extends EventEmitter {
  private static readonly TEMPLATES_KEY = '@document_templates';
  private static readonly GENERATED_DOCS_DIR = `${FileSystem.documentDirectory}generated_docs/`;
  
  private templates: Map<string, DocumentTemplate> = new Map();
  private defaultTemplates: DocumentTemplate[] = [];
  
  constructor() {
    super();
    this.initializeTemplates();
    this.ensureDirectories();
  }

  /**
   * Initialize default templates
   */
  private async initializeTemplates(): Promise<void> {
    // Load custom templates
    await this.loadTemplates();
    
    // Initialize default templates
    this.defaultTemplates = [
      this.createMedicalRecordTemplate(),
      this.createPrescriptionTemplate(),
      this.createLabReportTemplate(),
      this.createConsentFormTemplate(),
      this.createReferralLetterTemplate(),
    ];
    
    // Add default templates if not exists
    for (const template of this.defaultTemplates) {
      if (!this.templates.has(template.id)) {
        this.templates.set(template.id, template);
      }
    }
  }

  /**
   * Create medical record template
   */
  private createMedicalRecordTemplate(): DocumentTemplate {
    return {
      id: 'medical_record_basic',
      name: 'Basic Medical Record',
      category: 'medical',
      description: 'Standard medical record for patient information',
      fields: [
        {
          id: 'patient_name',
          name: 'patientName',
          type: 'text',
          label: 'Patient Name',
          required: true,
          placeholder: 'Enter patient full name',
        },
        {
          id: 'date_of_birth',
          name: 'dateOfBirth',
          type: 'date',
          label: 'Date of Birth',
          required: true,
        },
        {
          id: 'gender',
          name: 'gender',
          type: 'select',
          label: 'Gender',
          required: true,
          validation: {
            options: ['Male', 'Female', 'Other'],
          },
        },
        {
          id: 'blood_type',
          name: 'bloodType',
          type: 'select',
          label: 'Blood Type',
          required: false,
          validation: {
            options: ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'],
          },
        },
        {
          id: 'allergies',
          name: 'allergies',
          type: 'text',
          label: 'Known Allergies',
          required: false,
          placeholder: 'List any known allergies',
        },
        {
          id: 'medical_history',
          name: 'medicalHistory',
          type: 'text',
          label: 'Medical History',
          required: false,
          placeholder: 'Previous conditions, surgeries, etc.',
        },
        {
          id: 'current_medications',
          name: 'currentMedications',
          type: 'text',
          label: 'Current Medications',
          required: false,
          placeholder: 'List current medications',
        },
      ],
      layout: {
        sections: [
          {
            id: 'personal_info',
            title: 'Personal Information',
            fields: ['patient_name', 'date_of_birth', 'gender', 'blood_type'],
            columns: 2,
          },
          {
            id: 'medical_info',
            title: 'Medical Information',
            fields: ['allergies', 'medical_history', 'current_medications'],
            columns: 1,
          },
        ],
        header: {
          title: 'Medical Record',
          logo: true,
        },
        footer: {
          pageNumbers: true,
        },
      },
      styles: {
        theme: 'medical',
        colors: {
          primary: '#0066CC',
          secondary: '#4A90E2',
          text: '#333333',
          background: '#FFFFFF',
        },
        fonts: {
          heading: 'Helvetica-Bold',
          body: 'Helvetica',
        },
        spacing: 'normal',
      },
      metadata: {
        version: '1.0',
        createdAt: Date.now(),
        updatedAt: Date.now(),
        author: 'System',
        tags: ['medical', 'patient', 'record'],
      },
    };
  }

  /**
   * Create prescription template
   */
  private createPrescriptionTemplate(): DocumentTemplate {
    return {
      id: 'prescription_basic',
      name: 'Prescription Form',
      category: 'medical',
      description: 'Standard prescription form',
      fields: [
        {
          id: 'patient_name',
          name: 'patientName',
          type: 'text',
          label: 'Patient Name',
          required: true,
        },
        {
          id: 'prescription_date',
          name: 'prescriptionDate',
          type: 'date',
          label: 'Date',
          required: true,
          defaultValue: new Date().toISOString(),
        },
        {
          id: 'medication_name',
          name: 'medicationName',
          type: 'text',
          label: 'Medication',
          required: true,
        },
        {
          id: 'dosage',
          name: 'dosage',
          type: 'text',
          label: 'Dosage',
          required: true,
          placeholder: 'e.g., 500mg',
        },
        {
          id: 'frequency',
          name: 'frequency',
          type: 'text',
          label: 'Frequency',
          required: true,
          placeholder: 'e.g., Twice daily',
        },
        {
          id: 'duration',
          name: 'duration',
          type: 'text',
          label: 'Duration',
          required: true,
          placeholder: 'e.g., 7 days',
        },
        {
          id: 'instructions',
          name: 'instructions',
          type: 'text',
          label: 'Special Instructions',
          required: false,
        },
        {
          id: 'prescriber_signature',
          name: 'prescriberSignature',
          type: 'signature',
          label: 'Prescriber Signature',
          required: true,
        },
      ],
      layout: {
        sections: [
          {
            id: 'patient_section',
            fields: ['patient_name', 'prescription_date'],
            columns: 2,
          },
          {
            id: 'medication_section',
            title: 'Medication Details',
            fields: ['medication_name', 'dosage', 'frequency', 'duration'],
            columns: 2,
          },
          {
            id: 'instructions_section',
            fields: ['instructions'],
            columns: 1,
          },
          {
            id: 'signature_section',
            fields: ['prescriber_signature'],
            columns: 1,
          },
        ],
        header: {
          title: 'PRESCRIPTION',
          logo: true,
        },
      },
      styles: {
        theme: 'medical',
        colors: {
          primary: '#2E7D32',
          secondary: '#66BB6A',
          text: '#212121',
          background: '#FFFFFF',
        },
        fonts: {
          heading: 'Helvetica-Bold',
          body: 'Helvetica',
        },
        spacing: 'normal',
      },
      metadata: {
        version: '1.0',
        createdAt: Date.now(),
        updatedAt: Date.now(),
        author: 'System',
        tags: ['prescription', 'medication'],
      },
    };
  }

  /**
   * Create lab report template
   */
  private createLabReportTemplate(): DocumentTemplate {
    return {
      id: 'lab_report_basic',
      name: 'Laboratory Report',
      category: 'medical',
      description: 'Basic laboratory test report',
      fields: [
        {
          id: 'patient_name',
          name: 'patientName',
          type: 'text',
          label: 'Patient Name',
          required: true,
        },
        {
          id: 'patient_id',
          name: 'patientId',
          type: 'text',
          label: 'Patient ID',
          required: true,
        },
        {
          id: 'test_date',
          name: 'testDate',
          type: 'date',
          label: 'Test Date',
          required: true,
        },
        {
          id: 'test_type',
          name: 'testType',
          type: 'select',
          label: 'Test Type',
          required: true,
          validation: {
            options: ['Blood Test', 'Urine Test', 'X-Ray', 'CT Scan', 'MRI', 'Other'],
          },
        },
        {
          id: 'test_results',
          name: 'testResults',
          type: 'text',
          label: 'Test Results',
          required: true,
          placeholder: 'Enter detailed test results',
        },
        {
          id: 'normal_ranges',
          name: 'normalRanges',
          type: 'text',
          label: 'Normal Ranges',
          required: false,
          placeholder: 'Reference ranges',
        },
        {
          id: 'interpretation',
          name: 'interpretation',
          type: 'text',
          label: 'Clinical Interpretation',
          required: true,
        },
        {
          id: 'technician_name',
          name: 'technicianName',
          type: 'text',
          label: 'Lab Technician',
          required: true,
        },
      ],
      layout: {
        sections: [
          {
            id: 'patient_info',
            title: 'Patient Information',
            fields: ['patient_name', 'patient_id'],
            columns: 2,
          },
          {
            id: 'test_info',
            title: 'Test Information',
            fields: ['test_date', 'test_type'],
            columns: 2,
          },
          {
            id: 'results',
            title: 'Results',
            fields: ['test_results', 'normal_ranges'],
            columns: 1,
          },
          {
            id: 'interpretation_section',
            title: 'Clinical Interpretation',
            fields: ['interpretation'],
            columns: 1,
          },
          {
            id: 'certification',
            fields: ['technician_name'],
            columns: 1,
          },
        ],
        header: {
          title: 'LABORATORY REPORT',
          subtitle: 'Confidential Medical Document',
          logo: true,
        },
        footer: {
          text: 'This report is confidential and intended for medical use only',
          pageNumbers: true,
        },
      },
      styles: {
        theme: 'medical',
        colors: {
          primary: '#1976D2',
          secondary: '#42A5F5',
          text: '#212121',
          background: '#FFFFFF',
        },
        fonts: {
          heading: 'Helvetica-Bold',
          body: 'Helvetica',
        },
        spacing: 'normal',
      },
      metadata: {
        version: '1.0',
        createdAt: Date.now(),
        updatedAt: Date.now(),
        author: 'System',
        tags: ['lab', 'test', 'results'],
      },
    };
  }

  /**
   * Create consent form template
   */
  private createConsentFormTemplate(): DocumentTemplate {
    return {
      id: 'consent_form_basic',
      name: 'Medical Consent Form',
      category: 'legal',
      description: 'Standard medical procedure consent form',
      fields: [
        {
          id: 'patient_name',
          name: 'patientName',
          type: 'text',
          label: 'Patient Name',
          required: true,
        },
        {
          id: 'procedure_name',
          name: 'procedureName',
          type: 'text',
          label: 'Procedure/Treatment',
          required: true,
        },
        {
          id: 'procedure_description',
          name: 'procedureDescription',
          type: 'text',
          label: 'Description',
          required: true,
        },
        {
          id: 'risks_benefits',
          name: 'risksBenefits',
          type: 'text',
          label: 'Risks and Benefits',
          required: true,
        },
        {
          id: 'alternatives',
          name: 'alternatives',
          type: 'text',
          label: 'Alternative Treatments',
          required: false,
        },
        {
          id: 'consent_given',
          name: 'consentGiven',
          type: 'checkbox',
          label: 'I give my informed consent for this procedure',
          required: true,
        },
        {
          id: 'patient_signature',
          name: 'patientSignature',
          type: 'signature',
          label: 'Patient Signature',
          required: true,
        },
        {
          id: 'consent_date',
          name: 'consentDate',
          type: 'date',
          label: 'Date',
          required: true,
          defaultValue: new Date().toISOString(),
        },
        {
          id: 'witness_name',
          name: 'witnessName',
          type: 'text',
          label: 'Witness Name',
          required: true,
        },
        {
          id: 'witness_signature',
          name: 'witnessSignature',
          type: 'signature',
          label: 'Witness Signature',
          required: true,
        },
      ],
      layout: {
        sections: [
          {
            id: 'patient_section',
            title: 'Patient Information',
            fields: ['patient_name'],
          },
          {
            id: 'procedure_section',
            title: 'Procedure Information',
            fields: ['procedure_name', 'procedure_description', 'risks_benefits', 'alternatives'],
          },
          {
            id: 'consent_section',
            title: 'Consent',
            fields: ['consent_given'],
          },
          {
            id: 'signature_section',
            title: 'Signatures',
            fields: ['patient_signature', 'consent_date', 'witness_name', 'witness_signature'],
            columns: 2,
          },
        ],
        header: {
          title: 'INFORMED CONSENT FORM',
          logo: true,
        },
      },
      styles: {
        theme: 'formal',
        colors: {
          primary: '#424242',
          secondary: '#757575',
          text: '#212121',
          background: '#FFFFFF',
        },
        fonts: {
          heading: 'Times-Bold',
          body: 'Times-Roman',
        },
        spacing: 'normal',
      },
      metadata: {
        version: '1.0',
        createdAt: Date.now(),
        updatedAt: Date.now(),
        author: 'System',
        tags: ['consent', 'legal', 'medical'],
      },
    };
  }

  /**
   * Create referral letter template
   */
  private createReferralLetterTemplate(): DocumentTemplate {
    return {
      id: 'referral_letter',
      name: 'Medical Referral Letter',
      category: 'medical',
      description: 'Professional medical referral letter',
      fields: [
        {
          id: 'referring_doctor',
          name: 'referringDoctor',
          type: 'text',
          label: 'Referring Doctor',
          required: true,
        },
        {
          id: 'referring_clinic',
          name: 'referringClinic',
          type: 'text',
          label: 'Clinic/Hospital',
          required: true,
        },
        {
          id: 'referral_date',
          name: 'referralDate',
          type: 'date',
          label: 'Date',
          required: true,
          defaultValue: new Date().toISOString(),
        },
        {
          id: 'specialist_name',
          name: 'specialistName',
          type: 'text',
          label: 'To: Specialist Name',
          required: true,
        },
        {
          id: 'specialist_department',
          name: 'specialistDepartment',
          type: 'text',
          label: 'Department/Specialty',
          required: true,
        },
        {
          id: 'patient_name',
          name: 'patientName',
          type: 'text',
          label: 'Patient Name',
          required: true,
        },
        {
          id: 'patient_dob',
          name: 'patientDob',
          type: 'date',
          label: 'Patient DOB',
          required: true,
        },
        {
          id: 'reason_for_referral',
          name: 'reasonForReferral',
          type: 'text',
          label: 'Reason for Referral',
          required: true,
        },
        {
          id: 'clinical_history',
          name: 'clinicalHistory',
          type: 'text',
          label: 'Clinical History',
          required: true,
        },
        {
          id: 'current_medications',
          name: 'currentMedications',
          type: 'text',
          label: 'Current Medications',
          required: false,
        },
        {
          id: 'relevant_results',
          name: 'relevantResults',
          type: 'text',
          label: 'Relevant Test Results',
          required: false,
        },
        {
          id: 'urgency',
          name: 'urgency',
          type: 'select',
          label: 'Urgency',
          required: true,
          validation: {
            options: ['Routine', 'Urgent', 'Emergency'],
          },
        },
      ],
      layout: {
        sections: [
          {
            id: 'header_info',
            fields: ['referring_doctor', 'referring_clinic', 'referral_date'],
          },
          {
            id: 'recipient_info',
            title: 'To',
            fields: ['specialist_name', 'specialist_department'],
          },
          {
            id: 'patient_info',
            title: 'Patient Information',
            fields: ['patient_name', 'patient_dob'],
            columns: 2,
          },
          {
            id: 'referral_details',
            title: 'Referral Details',
            fields: ['reason_for_referral', 'clinical_history', 'current_medications', 'relevant_results', 'urgency'],
          },
        ],
        header: {
          title: 'MEDICAL REFERRAL',
          logo: true,
        },
      },
      styles: {
        theme: 'formal',
        colors: {
          primary: '#1565C0',
          secondary: '#1E88E5',
          text: '#212121',
          background: '#FFFFFF',
        },
        fonts: {
          heading: 'Helvetica-Bold',
          body: 'Helvetica',
        },
        spacing: 'normal',
      },
      metadata: {
        version: '1.0',
        createdAt: Date.now(),
        updatedAt: Date.now(),
        author: 'System',
        tags: ['referral', 'medical', 'letter'],
      },
    };
  }

  /**
   * Generate document from template
   */
  async generateDocument(
    templateId: string,
    data: Record<string, any>,
    format: 'pdf' | 'html' | 'docx' = 'pdf'
  ): Promise<GeneratedDocument> {
    const template = this.templates.get(templateId);
    if (!template) {
      throw new Error(`Template ${templateId} not found`);
    }
    
    // Validate required fields
    this.validateTemplateData(template, data);
    
    // Generate document based on format
    let filePath: string;
    switch (format) {
      case 'pdf':
        filePath = await this.generatePDF(template, data);
        break;
      case 'html':
        filePath = await this.generateHTML(template, data);
        break;
      case 'docx':
        filePath = await this.generateDOCX(template, data);
        break;
      default:
        throw new Error(`Unsupported format: ${format}`);
    }
    
    const generatedDoc: GeneratedDocument = {
      id: this.generateDocumentId(),
      templateId,
      data,
      format,
      generatedAt: Date.now(),
      filePath,
    };
    
    this.emit('document-generated', generatedDoc);
    return generatedDoc;
  }

  /**
   * Create custom template
   */
  async createTemplate(template: Omit<DocumentTemplate, 'metadata'>): Promise<DocumentTemplate> {
    const fullTemplate: DocumentTemplate = {
      ...template,
      metadata: {
        version: '1.0',
        createdAt: Date.now(),
        updatedAt: Date.now(),
        author: 'User',
        tags: [],
      },
    };
    
    this.templates.set(fullTemplate.id, fullTemplate);
    await this.saveTemplates();
    
    this.emit('template-created', fullTemplate);
    return fullTemplate;
  }

  /**
   * Update template
   */
  async updateTemplate(
    templateId: string,
    updates: Partial<DocumentTemplate>
  ): Promise<DocumentTemplate> {
    const template = this.templates.get(templateId);
    if (!template) {
      throw new Error(`Template ${templateId} not found`);
    }
    
    const updated: DocumentTemplate = {
      ...template,
      ...updates,
      metadata: {
        ...template.metadata,
        updatedAt: Date.now(),
      },
    };
    
    this.templates.set(templateId, updated);
    await this.saveTemplates();
    
    this.emit('template-updated', updated);
    return updated;
  }

  /**
   * Delete template
   */
  async deleteTemplate(templateId: string): Promise<void> {
    if (this.defaultTemplates.some(t => t.id === templateId)) {
      throw new Error('Cannot delete default template');
    }
    
    this.templates.delete(templateId);
    await this.saveTemplates();
    
    this.emit('template-deleted', { templateId });
  }

  /**
   * Get all templates
   */
  getTemplates(category?: DocumentTemplate['category']): DocumentTemplate[] {
    const templates = Array.from(this.templates.values());
    
    if (category) {
      return templates.filter(t => t.category === category);
    }
    
    return templates;
  }

  /**
   * Get template by ID
   */
  getTemplate(templateId: string): DocumentTemplate | undefined {
    return this.templates.get(templateId);
  }

  /**
   * Private helper methods
   */
  
  private async ensureDirectories(): Promise<void> {
    try {
      const dirInfo = await FileSystem.getInfoAsync(OfflineDocumentGenerator.GENERATED_DOCS_DIR);
      if (!dirInfo.exists) {
        await FileSystem.makeDirectoryAsync(OfflineDocumentGenerator.GENERATED_DOCS_DIR, {
          intermediates: true,
        });
      }
    } catch (error) {
      console.error('Failed to create directories:', error);
    }
  }

  private validateTemplateData(template: DocumentTemplate, data: Record<string, any>): void {
    for (const field of template.fields) {
      if (field.required && !data[field.name]) {
        throw new Error(`Required field missing: ${field.label}`);
      }
      
      if (data[field.name] && field.validation) {
        // Validate pattern
        if (field.validation.pattern) {
          const regex = new RegExp(field.validation.pattern);
          if (!regex.test(data[field.name])) {
            throw new Error(`Invalid format for field: ${field.label}`);
          }
        }
        
        // Validate options
        if (field.validation.options && !field.validation.options.includes(data[field.name])) {
          throw new Error(`Invalid option for field: ${field.label}`);
        }
        
        // Validate numeric ranges
        if (field.type === 'number') {
          const value = Number(data[field.name]);
          if (field.validation.min !== undefined && value < field.validation.min) {
            throw new Error(`Value too low for field: ${field.label}`);
          }
          if (field.validation.max !== undefined && value > field.validation.max) {
            throw new Error(`Value too high for field: ${field.label}`);
          }
        }
      }
    }
  }

  private async generatePDF(template: DocumentTemplate, data: Record<string, any>): Promise<string> {
    // In real implementation, would use a PDF generation library
    // For now, generate HTML and save as .pdf extension
    const html = await this.generateHTML(template, data);
    const pdfPath = html.replace('.html', '.pdf');
    
    // Simulate PDF generation
    await FileSystem.copyAsync({
      from: html,
      to: pdfPath,
    });
    
    return pdfPath;
  }

  private async generateHTML(template: DocumentTemplate, data: Record<string, any>): Promise<string> {
    const html = this.renderTemplateToHTML(template, data);
    const filePath = `${OfflineDocumentGenerator.GENERATED_DOCS_DIR}${this.generateDocumentId()}.html`;
    
    await FileSystem.writeAsStringAsync(filePath, html);
    return filePath;
  }

  private async generateDOCX(template: DocumentTemplate, data: Record<string, any>): Promise<string> {
    // In real implementation, would use a DOCX generation library
    // For now, generate HTML and save as .docx extension
    const html = await this.generateHTML(template, data);
    const docxPath = html.replace('.html', '.docx');
    
    // Simulate DOCX generation
    await FileSystem.copyAsync({
      from: html,
      to: docxPath,
    });
    
    return docxPath;
  }

  private renderTemplateToHTML(template: DocumentTemplate, data: Record<string, any>): string {
    const { styles, layout } = template;
    
    let html = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>${template.name}</title>
  <style>
    body {
      font-family: ${styles.fonts.body};
      color: ${styles.colors.text};
      background: ${styles.colors.background};
      margin: 0;
      padding: 20px;
      line-height: ${styles.spacing === 'compact' ? '1.4' : styles.spacing === 'relaxed' ? '1.8' : '1.6'};
    }
    h1, h2, h3 {
      font-family: ${styles.fonts.heading};
      color: ${styles.colors.primary};
    }
    .header {
      text-align: center;
      margin-bottom: 30px;
      border-bottom: 2px solid ${styles.colors.primary};
      padding-bottom: 20px;
    }
    .section {
      margin: 20px 0;
    }
    .section-title {
      font-size: 18px;
      font-weight: bold;
      color: ${styles.colors.primary};
      margin-bottom: 10px;
    }
    .field {
      margin: 10px 0;
    }
    .field-label {
      font-weight: bold;
      color: ${styles.colors.secondary};
    }
    .field-value {
      margin-left: 10px;
    }
    .columns-2 {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
    }
    .footer {
      margin-top: 40px;
      padding-top: 20px;
      border-top: 1px solid #ccc;
      text-align: center;
      font-size: 12px;
      color: #666;
    }
    .signature {
      border-bottom: 1px solid #000;
      width: 200px;
      height: 40px;
      margin: 10px 0;
    }
  </style>
</head>
<body>`;

    // Header
    if (layout.header) {
      html += `
  <div class="header">
    <h1>${layout.header.title}</h1>
    ${layout.header.subtitle ? `<p>${layout.header.subtitle}</p>` : ''}
  </div>`;
    }

    // Sections
    for (const section of layout.sections) {
      html += `
  <div class="section">`;
      
      if (section.title) {
        html += `
    <div class="section-title">${section.title}</div>`;
      }
      
      html += `
    <div class="${section.columns === 2 ? 'columns-2' : ''}">`;
      
      for (const fieldId of section.fields) {
        const field = template.fields.find(f => f.id === fieldId);
        if (field && data[field.name] !== undefined) {
          html += `
      <div class="field">
        <span class="field-label">${field.label}:</span>
        <span class="field-value">${
          field.type === 'signature' 
            ? '<div class="signature"></div>' 
            : field.type === 'checkbox'
            ? (data[field.name] ? '✓' : '☐')
            : data[field.name]
        }</span>
      </div>`;
        }
      }
      
      html += `
    </div>
  </div>`;
    }

    // Footer
    if (layout.footer) {
      html += `
  <div class="footer">
    ${layout.footer.text || ''}
    ${layout.footer.pageNumbers ? '<span>Page 1</span>' : ''}
  </div>`;
    }

    html += `
</body>
</html>`;

    return html;
  }

  private async loadTemplates(): Promise<void> {
    try {
      const stored = await AsyncStorage.getItem(OfflineDocumentGenerator.TEMPLATES_KEY);
      if (stored) {
        const templates = JSON.parse(stored);
        for (const template of templates) {
          this.templates.set(template.id, template);
        }
      }
    } catch (error) {
      console.error('Failed to load templates:', error);
    }
  }

  private async saveTemplates(): Promise<void> {
    try {
      const customTemplates = Array.from(this.templates.values()).filter(
        t => !this.defaultTemplates.some(dt => dt.id === t.id)
      );
      
      await AsyncStorage.setItem(
        OfflineDocumentGenerator.TEMPLATES_KEY,
        JSON.stringify(customTemplates)
      );
    } catch (error) {
      console.error('Failed to save templates:', error);
      throw error;
    }
  }

  private generateDocumentId(): string {
    return `doc_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
}

export default OfflineDocumentGenerator;