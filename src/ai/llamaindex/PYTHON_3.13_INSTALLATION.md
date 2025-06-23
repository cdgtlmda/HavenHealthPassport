# LlamaIndex Installation Guide for Python 3.13

## Issue
You're using Python 3.13.1, which is very new. The pinned version of LlamaIndex (0.10.12) only supports Python versions up to 3.11, causing installation failures.

## Solution

### Option 1: Use the Installation Script (Recommended)

1. First, activate your virtual environment:
   ```bash
   source venv/bin/activate  # On macOS/Linux
   # or
   venv\Scripts\activate  # On Windows
   ```

2. Navigate to the LlamaIndex directory:
   ```bash
   cd /Users/cadenceapeiron/Documents/HavenHealthPassport/src/ai/llamaindex
   ```

3. Run the installation script:
   ```bash
   ./install.sh
   ```

### Option 2: Manual Installation

1. Activate your virtual environment and navigate to the directory as above

2. Install core packages first:
   ```bash
   pip install llama-index llama-index-core
   ```

3. Install additional dependencies:
   ```bash
   pip install tiktoken openai pandas numpy httpx aiohttp pypdf Pillow
   pip install "SQLAlchemy[asyncio]>=2.0.0" aiosqlite nest-asyncio
   ```

### Option 3: Use Flexible Requirements

1. Activate your virtual environment and navigate to the directory

2. Install using the flexible requirements:
   ```bash
   pip install -r requirements-flexible.txt
   ```

## Verification

After installation, verify everything is working:

```bash
python verify_installation.py
```

## Troubleshooting

If you encounter issues:

1. **Ensure you're in the virtual environment**: Your prompt should show `(venv)`

2. **Upgrade pip first**:
   ```bash
   pip install --upgrade pip
   ```

3. **If specific packages fail**, install them individually:
   ```bash
   pip install package_name --no-deps
   ```

4. **For version conflicts**, let pip resolve them:
   ```bash
   pip install llama-index
   ```
   (without specifying a version)

## Next Steps

Once installation is complete:
1. Run the verification script
2. Update the checklist to mark this item as complete
3. Proceed to the next item: "Install vector store integrations"
