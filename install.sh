#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Installing mt-code..."

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
else
    echo "Virtual environment already exists."
fi

# Activate and install dependencies
echo "Installing dependencies..."
source venv/bin/activate
pip install -r requirements.txt

# Make mt-code executable
chmod +x mt-code

# Add to PATH
SHELL_RC=""
if [ -n "$ZSH_VERSION" ] || [ -f "$HOME/.zshrc" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -n "$BASH_VERSION" ] || [ -f "$HOME/.bashrc" ]; then
    SHELL_RC="$HOME/.bashrc"
fi

if [ -n "$SHELL_RC" ]; then
    if ! grep -q "mt-code" "$SHELL_RC" 2>/dev/null; then
        echo "" >> "$SHELL_RC"
        echo "# mt-code" >> "$SHELL_RC"
        echo "export PATH=\"$SCRIPT_DIR:\$PATH\"" >> "$SHELL_RC"
        echo "Added mt-code to PATH in $SHELL_RC"
        echo "Run 'source $SHELL_RC' or restart your terminal to use 'mt-code' command."
    else
        echo "mt-code already in PATH."
    fi
else
    echo "Could not detect shell config. Add this to your shell profile:"
    echo "  export PATH=\"$SCRIPT_DIR:\$PATH\""
fi

echo ""
echo "Installation complete!"
echo "Starting mt-code with welcome file..."
echo ""

# Run with welcome.txt
"$SCRIPT_DIR/mt-code" "$SCRIPT_DIR/welcome.txt"
