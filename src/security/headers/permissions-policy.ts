/**
 * Feature Policy / Permissions Policy Implementation
 * Modern permissions policy configuration
 */

/**
 * Permission features
 */
export type PermissionFeature =
  | 'accelerometer'
  | 'ambient-light-sensor'
  | 'autoplay'
  | 'battery'
  | 'camera'
  | 'cross-origin-isolated'
  | 'display-capture'
  | 'document-domain'
  | 'encrypted-media'
  | 'execution-while-not-rendered'
  | 'execution-while-out-of-viewport'
  | 'fullscreen'
  | 'geolocation'
  | 'gyroscope'
  | 'hid'
  | 'idle-detection'
  | 'interest-cohort'
  | 'keyboard-map'
  | 'magnetometer'
  | 'microphone'
  | 'midi'
  | 'navigation-override'
  | 'payment'
  | 'picture-in-picture'
  | 'publickey-credentials-get'
  | 'screen-wake-lock'
  | 'serial'
  | 'speaker-selection'
  | 'sync-xhr'
  | 'usb'
  | 'web-share'
  | 'xr-spatial-tracking';

/**
 * Permission directive values
 */
export type PermissionValue = '*' | 'self' | 'none' | string;

/**
 * Permissions policy configuration
 */
export interface PermissionsPolicyConfig {
  [feature: string]: PermissionValue[];
}

/**
 * Permissions policy builder
 */
export class PermissionsPolicyBuilder {
  private policy: PermissionsPolicyConfig = {};

  /**
   * Allow feature for specific origins
   */
  allow(feature: PermissionFeature, ...origins: PermissionValue[]): this {
    this.policy[feature] = origins;
    return this;
  }

  /**
   * Deny feature completely
   */
  deny(feature: PermissionFeature): this {
    this.policy[feature] = [];
    return this;
  }

  /**
   * Allow feature for same origin only
   */
  allowSelf(feature: PermissionFeature): this {
    this.policy[feature] = ['self'];
    return this;
  }

  /**
   * Allow feature for all origins
   */
  allowAll(feature: PermissionFeature): this {
    this.policy[feature] = ['*'];
    return this;
  }

  /**
   * Build policy string
   */
  build(): string {
    const directives: string[] = [];

    for (const [feature, values] of Object.entries(this.policy)) {
      if (values.length === 0) {
        directives.push(`${feature}=()`);
      } else {
        const formattedValues = values.map(v => {
          if (v === 'self' || v === 'none') return `'${v}'`;
          if (v === '*') return v;
          return `"${v}"`;
        });
        directives.push(`${feature}=(${formattedValues.join(' ')})`);
      }
    }

    return directives.join(', ');
  }

  /**
   * Build Feature-Policy header (legacy)
   */
  buildLegacy(): string {
    const directives: string[] = [];

    for (const [feature, values] of Object.entries(this.policy)) {
      if (values.length === 0) {
        directives.push(`${feature} 'none'`);
      } else {
        directives.push(`${feature} ${values.join(' ')}`);
      }
    }

    return directives.join('; ');
  }
}

/**
 * Healthcare-specific permissions policies
 */
export const HealthcarePermissionsPolicies = {
  // Patient portal - restrictive
  patientPortal: new PermissionsPolicyBuilder()
    .deny('camera')
    .deny('microphone')
    .deny('geolocation')
    .deny('usb')
    .deny('serial')
    .deny('hid')
    .deny('bluetooth')
    .deny('payment')
    .allowSelf('fullscreen')
    .deny('autoplay')
    .deny('display-capture')
    .build(),

  // Provider app - allows medical device access
  providerApp: new PermissionsPolicyBuilder()
    .allowSelf('camera') // For telehealth
    .allowSelf('microphone') // For telehealth
    .allowSelf('geolocation') // For emergency location
    .allowSelf('usb') // For medical devices
    .allowSelf('serial') // For medical devices
    .allowSelf('hid') // For medical devices
    .deny('payment')
    .allowSelf('fullscreen')
    .allowSelf('display-capture') // For screen sharing
    .build(),

  // Telehealth specific
  telehealth: new PermissionsPolicyBuilder()
    .allowSelf('camera')
    .allowSelf('microphone')
    .allowSelf('fullscreen')
    .allowSelf('display-capture')
    .allowSelf('picture-in-picture')
    .deny('geolocation')
    .deny('usb')
    .deny('payment')
    .build(),

  // API only
  api: new PermissionsPolicyBuilder()
    .deny('camera')
    .deny('microphone')
    .deny('geolocation')
    .deny('payment')
    .deny('usb')
    .deny('fullscreen')
    .build()
};

// Export convenience function
export const createPermissionsPolicy = () => new PermissionsPolicyBuilder();
