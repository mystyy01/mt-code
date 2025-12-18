# Disable Oh-My-Zsh, plugins, and fancy prompts
export ZSH_DISABLE_COMPFIX=true
export PROMPT='%~ > '  # simple path prompt
unsetopt PROMPT_SP
setopt NO_BEEP

# Disable echo
stty -echo 2>/dev/null