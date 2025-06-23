#!/bin/bash
# Bastion Host Configuration Script

# Update system
yum update -y

# Install essential packages
yum install -y amazon-cloudwatch-agent aws-cli jq

# Configure SSH hardening
cat >> /etc/ssh/sshd_config <<EOF

# SSH Hardening
Protocol 2
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
PermitEmptyPasswords no
X11Forwarding no
MaxAuthTries 3
ClientAliveInterval 300
ClientAliveCountMax 2
AllowUsers ec2-user
EOF

# Restart SSH service
systemctl restart sshd

# Configure CloudWatch logs
cat > /opt/aws/amazon-cloudwatch-agent/etc/config.json <<EOF
{
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [{
          "file_path": "/var/log/secure",
          "log_group_name": "/aws/bastion/${project_name}/secure",
          "log_stream_name": "{instance_id}"
        }]
      }
    }
  }
}
EOF

# Start CloudWatch agent
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
  -a fetch-config -m ec2 -s -c file:/opt/aws/amazon-cloudwatch-agent/etc/config.json

echo "Bastion host setup complete"
