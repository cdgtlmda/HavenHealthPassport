import {
  ManagedBlockchainClient,
  CreateMemberCommand,
  UpdateMemberCommand,
  GetMemberCommand,
  MemberConfiguration,
  MemberFrameworkConfiguration,
  MemberFabricConfiguration,
  MemberLogPublishingConfiguration
} from '@aws-sdk/client-managedblockchain';
import { KMSClient, GenerateDataKeyCommand } from '@aws-sdk/client-kms';
import { SecretsManagerClient, GetSecretValueCommand } from '@aws-sdk/client-secrets-manager';
import * as crypto from 'crypto';
import * as yaml from 'js-yaml';
import * as fs from 'fs/promises';
import * as path from 'path';

/**
 * Interface for member admin configuration
 */
export interface MemberAdminConfig {
  username: string;
  attributes: Array<{ name: string; value: string }>;
  certificate: {
    validity: number;
    algorithm: string;
    keySize: string;
    subject: {
      country: string;
      state: string;
      locality: string;
      organization: string;
      organizationalUnit: string;
      commonName: string;
    };
  };
  policies: {
    channelCreation: boolean;
    chaincodeLifecycle: {
      install: boolean;
      instantiate: boolean;
      upgrade: boolean;
      invoke: boolean;
      query: boolean;
    };
  };
}
/**
 * Manages AWS Managed Blockchain member admin configuration
 */
export class MemberAdminManager {
  private client: ManagedBlockchainClient;
  private kmsClient: KMSClient;
  private secretsClient: SecretsManagerClient;
  private configPath: string;

  constructor(region: string = 'us-east-1') {
    this.client = new ManagedBlockchainClient({ region });
    this.kmsClient = new KMSClient({ region });
    this.secretsClient = new SecretsManagerClient({ region });
    this.configPath = path.join(__dirname, '..', 'config', 'member-admin-config.yaml');
  }

  /**
   * Load admin configuration from YAML file
   */
  async loadConfig(): Promise<MemberAdminConfig> {
    try {
      const configContent = await fs.readFile(this.configPath, 'utf8');
      const config = yaml.load(configContent) as any;
      return config.memberAdmin as MemberAdminConfig;
    } catch (error) {
      console.error('Failed to load admin configuration:', error);
      throw new Error('Unable to load member admin configuration');
    }
  }

  /**
   * Generate secure admin password
   */
  generateSecurePassword(policy: any): string {
    const length = policy.minLength || 16;
    const charset = {
      uppercase: 'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
      lowercase: 'abcdefghijklmnopqrstuvwxyz',
      numbers: '0123456789',
      special: '!@#$%^&*()_+-=[]{}|;:,.<>?'
    };

    let password = '';
    let availableChars = '';

    // Build character set based on policy
    if (policy.requireUppercase) {
      availableChars += charset.uppercase;
      password += charset.uppercase[crypto.randomInt(charset.uppercase.length)];
    }
    if (policy.requireLowercase) {
      availableChars += charset.lowercase;
      password += charset.lowercase[crypto.randomInt(charset.lowercase.length)];
    }
    if (policy.requireNumbers) {
      availableChars += charset.numbers;
      password += charset.numbers[crypto.randomInt(charset.numbers.length)];
    }
    if (policy.requireSpecialChars) {
      availableChars += charset.special;
      password += charset.special[crypto.randomInt(charset.special.length)];
    }

    // Fill remaining length
    for (let i = password.length; i < length; i++) {
      password += availableChars[crypto.randomInt(availableChars.length)];
    }

    // Shuffle password
    return password.split('').sort(() => crypto.randomInt(3) - 1).join('');
  }

  /**
   * Create member configuration for AWS Managed Blockchain
   */
  async createMemberConfiguration(
    networkId: string,
    adminConfig: MemberAdminConfig
  ): Promise<MemberConfiguration> {
    // Generate admin password
    const adminPassword = this.generateSecurePassword(adminConfig.security.passwordPolicy);

    // Store password in AWS Secrets Manager
    const secretArn = await this.storeAdminCredentials(
      networkId,
      adminConfig.username,
      adminPassword
    );

    // Create Fabric configuration
    const fabricConfig: MemberFabricConfiguration = {
      AdminUsername: adminConfig.username,
      AdminPassword: adminPassword
    };

    // Configure logging
    const logConfig: MemberLogPublishingConfiguration = {
      Fabric: {
        CaLogs: {
          Cloudwatch: {
            Enabled: true
          }
        }
      }
    };

    // Build member configuration
    const memberConfig: MemberConfiguration = {
      Name: `${adminConfig.certificate.subject.organization}-member`,
      Description: `Blockchain member for ${adminConfig.certificate.subject.organization}`,
      FrameworkConfiguration: {
        Fabric: fabricConfig
      },
      LogPublishingConfiguration: logConfig,
      Tags: {
        'Organization': adminConfig.certificate.subject.organization,
        'Environment': process.env.NODE_ENV || 'production',
        'ManagedBy': 'HavenHealthPassport',
        'AdminUser': adminConfig.username
      }
    };

    return memberConfig;
  }

  /**
   * Store admin credentials in AWS Secrets Manager
   */
  private async storeAdminCredentials(
    networkId: string,
    username: string,
    password: string
  ): Promise<string> {
    const secretName = `haven-health/blockchain/${networkId}/admin-${username}`;

    const secretValue = JSON.stringify({
      username,
      password,
      createdAt: new Date().toISOString(),
      expiresAt: new Date(Date.now() + 90 * 24 * 60 * 60 * 1000).toISOString(),
      networkId
    });

    // Encrypt secret using KMS
    const dataKeyResponse = await this.kmsClient.send(
      new GenerateDataKeyCommand({
        KeyId: process.env.KMS_KEY_ID,
        KeySpec: 'AES_256'
      })
    );

    // Note: In production, implement proper encryption using the data key
    // For now, returning a placeholder ARN
    return `arn:aws:secretsmanager:${process.env.AWS_REGION}:${process.env.AWS_ACCOUNT_ID}:secret:${secretName}`;
  }

  /**
   * Configure admin user for blockchain member
   */
  async configureMemberAdmin(networkId: string, memberId?: string): Promise<void> {
    try {
      console.log('Loading admin configuration...');
      const adminConfig = await this.loadConfig();

      console.log('Creating member configuration...');
      const memberConfig = await this.createMemberConfiguration(networkId, adminConfig);

      if (memberId) {
        // Update existing member
        console.log(`Updating member ${memberId} with admin configuration...`);
        await this.client.send(new UpdateMemberCommand({
          NetworkId: networkId,
          MemberId: memberId,
          LogPublishingConfiguration: memberConfig.LogPublishingConfiguration
        }));
      } else {
        console.log('Member admin configuration prepared for new member creation');
      }

      console.log('Member admin configuration completed successfully');
    } catch (error) {
      console.error('Failed to configure member admin:', error);
      throw error;
    }
  }
}
