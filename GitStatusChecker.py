import subprocess

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

if __name__ == "__main__":
    repo_path = "/path/to/your/repo"
    
    branch = get_current_branch(repo_path)
    if branch:
        print(f"The currently checked-out branch in repository '{repo_path}' is '{branch}'")
    else:
        print(f"Could not determine the currently checked-out branch in repository '{repo_path}'")

# Run the checks
if __name__ == "__main__":
    repo_path = "C:/Git/Unseen"
    branch_to_check = "main-reorg"
    
    if check_unpushed_commits(repo_path, branch_to_check):
        print(f"There are unpushed commits on branch '{branch_to_check}' in repository '{repo_path}'")
    else:
        print(f"All commits on branch '{branch_to_check}' in repository '{repo_path}' have been pushed")
