"""Helper script to update requirements.txt with current package versions."""
import pkg_resources
import re
from pathlib import Path

def get_installed_version(package_name):
    """Get the installed version of a package."""
    try:
        return pkg_resources.get_distribution(package_name).version
    except pkg_resources.DistributionNotFound:
        return None

def update_requirements():
    """Update requirements.txt with currently installed package versions."""
    requirements_path = Path("requirements.txt")
    if not requirements_path.exists():
        print("requirements.txt not found")
        return
        
    # Read current requirements
    with open(requirements_path) as f:
        lines = f.readlines()
        
    # Update versions
    updated_lines = []
    for line in lines:
        # Skip comments and empty lines
        if line.startswith("#") or not line.strip():
            updated_lines.append(line)
            continue
            
        # Get package name
        match = re.match(r'^([^>=<\s]+)', line.strip())
        if match:
            package_name = match.group(1)
            version = get_installed_version(package_name)
            if version:
                updated_lines.append(f"{package_name}>={version}\n")
            else:
                updated_lines.append(line)
        else:
            updated_lines.append(line)
            
    # Write updated requirements
    with open(requirements_path, 'w') as f:
        f.writelines(updated_lines)
        
if __name__ == '__main__':
    update_requirements()
