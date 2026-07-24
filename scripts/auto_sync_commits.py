#!/usr/bin/env python3
import subprocess
import os

def run_git_command(cmd):
    """Execute a git command and return (returncode, stdout, stderr)"""
    result = subprocess.run(cmd, capture_output=True, text=True, cwd='/home/opc/projects/motus.leap')
    return result.returncode, result.stdout, result.stderr

def main():
    # Check if this is a git repository
    returncode, stdout, stderr = run_git_command(['git', 'rev-parse', '--git-dir'])
    if returncode != 0:
        print("Error: motus.leap is not a git repository")
        return
    
    # Check for uncommitted changes
    returncode, stdout, stderr = run_git_command(['git', 'status', '--porcelain'])
    if returncode != 0:
        print("Error checking git status")
        return
    
    if stdout.strip():
        # Stage all changes
        returncode, stdout, stderr = run_git_command(['git', 'add', '.'])
        if returncode != 0:
            print(f"Error staging changes: {stderr}")
            return
            
        # Create commit with timestamp
        timestamp = os.popen('date +"%Y-%m-%d %H:%M:%S"').read().strip()
        commit_message = f"auto-sync commit: {timestamp}"
        
        returncode, stdout, stderr = run_git_command(['git', 'commit', '-m', commit_message])
        if returncode != 0:
            print(f"Error committing: {stderr}")
        else:
            print(f"Successfully committed: {commit_message}")
    else:
        print("No changes to commit - working tree is clean")

if __name__ == "__main__":
    main()