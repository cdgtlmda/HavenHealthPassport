/**
 * Consensus Configuration Integration
 * Haven Health Passport - Blockchain Infrastructure
 *
 * Integrates consenter set with election parameters
 */

import { ConsenterSetConfig } from './consenter-set-generator';
import { ElectionParametersConfig } from './election-parameters';

export interface IntegratedConsensusConfig {
  consenterSet: ConsenterSetConfig;
  electionParameters: ElectionParametersConfig;
  ordererConfiguration: OrdererConfig;
}

export interface OrdererConfig {
  General: {
    ListenAddress: string;
    ListenPort: number;
    TLS: {
      Enabled: boolean;
      ClientAuthRequired: boolean;
      Cert: string;
      Key: string;
      ClientRootCAs: string[];
    };
  };
  Consensus: {
    Type: 'etcdraft';
    EtcdRaft: {
      Consenters: Array<{
        Host: string;
        Port: number;
        ClientTLSCert: string;
        ServerTLSCert: string;
      }>;
      Options: {
        TickInterval: string;
        ElectionTick: number;
        HeartbeatTick: number;
        MaxInflightBlocks: number;
        SnapshotIntervalSize: number;
      };
    };
  };
}
