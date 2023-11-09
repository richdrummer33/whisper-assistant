import subprocess

global_repo_path = "C:/Git/Unseen"

# Check for unpushed commits
def check_unpushed_commits(repo_path, branch="main"):
    """
    Check if there are any unpushed commits on the given branch in the given repository.
    """
    try:
        # Navigate to the repository directory
        subprocess.check_call(["git", "-C", repo_path, "fetch"])  # Ensure we have the latest info from remote
        
        # Check for unpushed commits
        result = subprocess.check_output(
            ["git", "-C", repo_path, "rev-list", f"{branch}..{branch}@{{u}}"],
            stderr=subprocess.STDOUT
        )
        
        commits = result.decode("utf-8").strip().split('\n')
        if commits and commits[0]:  # If there's any output, there are unpushed commits
            return True
        return False
    except subprocess.CalledProcessError as e:
        print(f"Error: {e.output.decode('utf-8')}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False
    
import subprocess

# Get the current working branch
def get_current_branch(repo_path):
    """
    Get the currently checked-out branch in the given repository.
    """
    try:
        result = subprocess.check_output(
            ["git", "-C", repo_path, "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.STDOUT
        )
        
        current_branch = result.decode("utf-8").strip()
        return current_branch
    except subprocess.CalledProcessError as e:
        print(f"Error: {e.output.decode('utf-8')}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None

import tkinter as tk
from tkinter import messagebox

def show_message_and_wait(title, message):
    root = tk.Tk()
    root.withdraw()  # Hides the root window
    messagebox.showinfo(title, message)
    root.mainloop()
    
def status_check():
    # 1. check current branch state
    current_branch = get_current_branch(global_repo_path)
    
    if check_unpushed_commits(global_repo_path, current_branch):
        print(f"There are unpushed commits on branch '{current_branch}' in repository '{global_repo_path}'")
        show_message_and_wait("Unpushed commits", f"There are unpushed commits on branch '{current_branch}'")
    else:
        print(f"All commits on branch '{current_branch}' in repository '{global_repo_path}' have been pushed")
    
    # 2. check main branch state
    branch_to_check = "main-reorg"
    
    if check_unpushed_commits(global_repo_path, branch_to_check):
        print(f"There are unpushed commits on branch '{branch_to_check}' in repository '{global_repo_path}'")
        show_message_and_wait("Unpushed commits", f"There are unpushed commits on branch '{branch_to_check}'")
    else:
        print(f"All commits on branch '{branch_to_check}' in repository '{global_repo_path}' have been pushed")


if __name__ == "__main__":
    status_check()