#!/bin/bash

# Pterodactyl Minecraft Server Installer Script
# Author: Dashtiss
# Version: 1.3.2 (Aligned with individual scripts, added snapshot support)
# Description: Installs Minecraft (Vanilla, Fabric, Forge, NeoForge) based on environment variables.
#              Designed for use in a Pterodactyl Egg's install script.
#
# Required Environment Variables:
#   MINECRAFT_VERSION   (e.g., "1.20.1", "1.19.4", "latest", "snapshot")
#   MOD_LOADER_TYPE     (e.g., "vanilla", "fabric", "forge", "neoforge")
#   SERVER_JARFILE      (e.g., "server.jar") - The name of the server JAR file to use in startup command
#
# Optional Environment Variables:
#   MODLOADER_VERSION   (e.g., "0.15.7" for Fabric, "47.1.0" or "1.20.1-47.1.0" for Forge, "20.4.85-beta" for NeoForge, "latest", "snapshot")
#                       - Specific version for the chosen mod loader. If "latest" or "snapshot", attempts to auto-detect.
#   FABRIC_INSTALLER_VERSION (e.g., "0.11.2", "latest") - Specific Fabric installer JAR version. Defaults to a known stable one.
#                       - Only used if MOD_LOADER_TYPE is "fabric".

echo -e "\e[1;34m[INFO] Starting Minecraft server installation script...\e[0m"

# --- Basic Startup ---
# Ensure necessary system packages are updated and installed.
apt update
apt install -y curl jq unzip dos2unix wget

# Create and navigate to the server directory.
mkdir -p /mnt/server
cd /mnt/server || { echo -e "\e[31m[ERROR] Could not change to server directory: /mnt/server\e[0m"; exit 1; }

# --- Configuration ---
SERVER_DIR="/mnt/server" # Pterodactyl's standard server directory
JAVA_ARGS_FILE="${SERVER_DIR}/user_jvm_args.txt" # Common name for user-defined JVM args
EULA_FILE="${SERVER_DIR}/eula.txt"
INSTALLER_JAR_NAME="installer.jar" # Temporary name for downloaded installers
SERVER_JAR="${SERVER_JARFILE:-server.jar}" # Use SERVER_JARFILE if set, default to server.jar if not

# --- Helper Functions ---
print_error() {
  echo -e "\e[31m[ERROR] $1\e[0m"
  exit 1
}

print_warning() {
  echo -e "\e[33m[WARN] $1\e[0m"
}

print_info() {
  echo -e "\e[32m[INFO] $1\e[0m"
}

# Function to check if a command exists
command_exists() {
  command -v "$1" >/dev/null 2>&1
}

# Ensure necessary tools are available
check_dependencies() {
  print_info "Checking dependencies (curl, jq, java)..."
  if ! command_exists curl; then
    print_error "curl is not installed. Please add it to your egg's Docker image."
  fi
  if ! command_exists jq; then
    print_error "jq is not installed. Please add it to your egg's Docker image."
  fi
  if ! command_exists java; then
    print_error "java is not installed. Please add it to your egg's Docker image."
  fi
  print_info "All critical dependencies found."
}

# Function to get the latest Minecraft version (release or snapshot)
get_latest_minecraft_version() {
  local version_type="$1" # "release" or "snapshot"
  local version_manifest_list_url="https://launchermeta.mojang.com/mc/game/version_manifest_v2.json" 
  
  # Redirect print_info calls to stderr so they don't pollute stdout (which is captured by assignment)
  print_info "Fetching latest Minecraft ${version_type} version from Mojang manifest (URL: ${version_manifest_list_url})..." >&2 
  local manifest_list_json=$(curl -sSLf "$version_manifest_list_url")
  if [ $? -ne 0 ] || [ -z "$manifest_list_json" ]; then
    print_error "Failed to fetch version manifest list from Mojang to determine latest Minecraft version." >&2
  fi

  local latest_mc_version=""
  if [ "$version_type" == "release" ]; then
    latest_mc_version=$(echo "$manifest_list_json" | jq -r '.latest.release')
  elif [ "$version_type" == "snapshot" ]; then
    latest_mc_version=$(echo "$manifest_list_json" | jq -r '.latest.snapshot')
  fi

  if [ -z "$latest_mc_version" ] || [ "$latest_mc_version" == "null" ]; then
    print_error "Could not determine the latest Minecraft ${version_type} version from Mojang manifest." >&2
  fi
  echo "$latest_mc_version" # Only echo the version number to stdout
}

check_minecraft_version_validity() {
    local version="$1"
    local version_manifest_list_url="https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
    
    print_info "Validating Minecraft version ${version}..."
    local manifest_list_json=$(curl -sSLf "$version_manifest_list_url")
    if [ $? -ne 0 ] || [ -z "$manifest_list_json" ]; then
        print_error "Failed to fetch version manifest list from Mojang for validation."
    fi

    # Check if the version exists in the manifest
    local version_exists=$(echo "$manifest_list_json" | jq -r --arg VERSION "$version" '.versions[] | select(.id == $VERSION) | .id')
    if [ -z "$version_exists" ]; then
        print_error "Minecraft version ${version} does not exist or is not yet released. Please check the version number or use an older version."
    fi
    
    # For very new versions, check if it's pre-release/snapshot and warn user only for non-vanilla
    local version_type=$(echo "$manifest_list_json" | jq -r --arg VERSION "$version" '.versions[] | select(.id == $VERSION) | .type')
    if [ "$version_type" = "snapshot" ] || [ "$version_type" = "pre_release" ]; then
        if [ "${MOD_LOADER_TYPE}" != "vanilla" ]; then
            print_warning "Warning: ${version} is a ${version_type}. It may not be supported by mod loaders yet."
        fi
    fi
    
    return 0
}

check_modloader_compatibility() {
    local mc_version="$1"
    local loader_type="$2"

    # Vanilla always supports any valid Minecraft version
    if [ "${loader_type}" == "vanilla" ]; then
        print_info "Vanilla installation selected - compatible with all Minecraft versions"
        return 0
    fi

    case "${loader_type}" in
        fabric)
            # First check if Fabric supports this version by trying to fetch loader versions
            local fabric_game_versions_url="https://meta.fabricmc.net/v2/versions/game/yarn"
            local fabric_versions=$(curl -sSLf "$fabric_game_versions_url" || echo "")
            if [ -z "$fabric_versions" ]; then
                print_warning "Could not verify Fabric compatibility - API may be down. Continuing anyway..."
                return 0
            fi
            
            local version_supported=$(echo "$fabric_versions" | jq -r --arg VERSION "$mc_version" '.[] | select(.gameVersion == $VERSION) | .gameVersion')
            if [ -z "$version_supported" ]; then
                # Fallback to checking loader versions directly
                local fabric_loader_versions_url="https://meta.fabricmc.net/v2/versions/loader/${mc_version}"
                local loader_check=$(curl -sSLf "$fabric_loader_versions_url" || echo "")
                if [ -z "$loader_check" ] || [ "$loader_check" == "[]" ]; then
                    print_warning "Minecraft version ${mc_version} might not be supported by Fabric yet. Installation may fail."
                    return 0
                fi
            fi
            ;;
        forge)
            # First try checking promotions data
            local forge_meta=$(curl -sSLf "https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json" || echo "")
            if [ -n "$forge_meta" ]; then
                local has_version=$(echo "$forge_meta" | jq -r --arg VERSION "$mc_version" 'keys[] | select(startswith($VERSION))' | head -n1)
                if [ -n "$has_version" ]; then
                    return 0
                fi
            fi
            
            print_warning "Could not verify Forge compatibility for ${mc_version}. Installation may fail if version is not supported."
            return 0
            ;;
        neoforge)
            # Check NeoForge compatibility
            local neoforge_meta=$(curl -sSLf "https://maven.neoforged.net/releases/net/neoforged/neoforge/promotions_slim.json" || echo "")
            if [ -z "$neoforge_meta" ]; then
                print_warning "Could not verify NeoForge compatibility - API may be down. Continuing anyway..."
                return 0
            fi
            
            local has_version=$(echo "$neoforge_meta" | jq -r --arg VERSION "$mc_version" 'keys[] | select(startswith($VERSION))' | head -n1)
            if [ -z "$has_version" ]; then
                print_warning "Minecraft version ${mc_version} might not be supported by NeoForge yet. Installation may fail."
                return 0
            fi
            ;;
        *)
            print_error "Unknown mod loader type: ${loader_type}"
            ;;
    esac
    print_info "Minecraft version ${mc_version} appears compatible with ${loader_type}."
    return 0
}

check_env_vars() {
  print_info "Validating environment variables..."
  if [ -z "${MINECRAFT_VERSION}" ]; then
    print_error "MINECRAFT_VERSION environment variable is not set."
  fi
  if [ -z "${MOD_LOADER_TYPE}" ]; then
    print_error "MOD_LOADER_TYPE environment variable is not set. Use 'vanilla', 'fabric', 'forge', or 'neoforge'."
  fi
  MOD_LOADER_TYPE=$(echo "${MOD_LOADER_TYPE}" | tr '[:upper:]' '[:lower:]') # Convert to lowercase

  # Resolve "latest" or "snapshot" for Minecraft version early if needed
  if [ "${MINECRAFT_VERSION}" == "latest" ]; then
    print_info "MINECRAFT_VERSION set to 'latest'. Auto-detecting latest release..."
    # Capture the output of the function into a temporary variable
    local resolved_mc_version=$(get_latest_minecraft_version "release")
    if [ -z "$resolved_mc_version" ]; then
      print_error "Failed to resolve 'latest' Minecraft version."
    fi
    MINECRAFT_VERSION="$resolved_mc_version" # Assign the clean version to MINECRAFT_VERSION
    print_info "Resolved MINECRAFT_VERSION to: ${MINECRAFT_VERSION}"
  elif [ "${MINECRAFT_VERSION}" == "snapshot" ]; then
    print_info "MINECRAFT_VERSION set to 'snapshot'. Auto-detecting latest snapshot..."
    local resolved_mc_version=$(get_latest_minecraft_version "snapshot")
    if [ -z "$resolved_mc_version" ]; then
      print_error "Failed to resolve 'snapshot' Minecraft version."
    fi
    MINECRAFT_VERSION="$resolved_mc_version"
    print_info "Resolved MINECRAFT_VERSION to: ${MINECRAFT_VERSION}"
  fi

  # After MINECRAFT_VERSION is resolved (either from direct input or latest/snapshot)
  # Validate the Minecraft version exists
  check_minecraft_version_validity "${MINECRAFT_VERSION}"
  
  # Check if the chosen modloader supports this version
  check_modloader_compatibility "${MINECRAFT_VERSION}" "${MOD_LOADER_TYPE}"

  print_info "Minecraft Version: ${MINECRAFT_VERSION}"
  print_info "Mod Loader Type: ${MOD_LOADER_TYPE}"
  [ -n "${MODLOADER_VERSION}" ] && print_info "Modloader Version: ${MODLOADER_VERSION}"
  if [ "${MOD_LOADER_TYPE}" == "fabric" ] && [ -n "${FABRIC_INSTALLER_VERSION}" ]; then
    print_info "Fabric Installer Version: ${FABRIC_INSTALLER_VERSION}"
  fi
}

# Function to download files with retries and error handling
download_file() {
  local url="$1"
  local output_path="$2"
  local max_retries=3
  local attempt=1

  print_info "Downloading $url to $output_path..."
  while [ $attempt -le $max_retries ]; do
    # Use -L to follow redirects, -f to fail silently on server errors (we check $? manually)
    curl -sSLf -o "$output_path" "$url"
    local curl_exit_code=$?
    if [ $curl_exit_code -eq 0 ] && [ -s "$output_path" ]; then
      print_info "Download successful."
      return 0
    elif [ $curl_exit_code -eq 22 ]; then # HTTP 4xx/5xx error
        print_warning "HTTP error during download (URL: $url). Attempt $attempt/$max_retries."
    else
      print_warning "Download attempt $attempt/$max_retries failed (curl code: $curl_exit_code). Retrying in 5 seconds..."
    fi
    sleep 5
    ((attempt++))
  done
  print_error "Failed to download $url after $max_retries attempts."
  return 1
}

# --- Installation Functions ---

install_vanilla() {
  print_info "Starting Vanilla Minecraft server installation for ${MINECRAFT_VERSION}..."
  local version_manifest_list_url="https://launchermeta.mojang.com/mc/game/version_manifest_v2.json" 
  
  print_info "Fetching version manifest list..."
  local manifest_list_json=$(curl -sSLf "$version_manifest_list_url")
  if [ $? -ne 0 ] || [ -z "$manifest_list_json" ]; then
    print_error "Failed to fetch version manifest list from Mojang."
  fi

  local version_url=$(echo "$manifest_list_json" | jq -r --arg MC_VERSION "$MINECRAFT_VERSION" '.versions[] | select(.id == $MC_VERSION) | .url')
  if [ -z "$version_url" ] || [ "$version_url" == "null" ]; then
    print_error "Could not find Minecraft version ${MINECRAFT_VERSION} in the Mojang manifest. Please check the version number."
  fi

  print_info "Fetching details for version ${MINECRAFT_VERSION} from ${version_url}..."
  local version_data_json=$(curl -sSLf "$version_url")
    if [ $? -ne 0 ] || [ -z "$version_data_json" ]; then
    print_error "Failed to fetch version data for ${MINECRAFT_VERSION}."
  fi

  local server_jar_url=$(echo "$version_data_json" | jq -r '.downloads.server.url')
  if [ -z "$server_jar_url" ] || [ "$server_jar_url" == "null" ]; then
    print_error "Could not find server JAR URL for Minecraft ${MINECRAFT_VERSION}."
  fi

  download_file "$server_jar_url" "${SERVER_DIR}/minecraft_server.${MINECRAFT_VERSION}.jar"
  standardize_server_jar "minecraft_server.${MINECRAFT_VERSION}.jar"
  
  export SERVER_JAR="server.jar"
  print_info "Vanilla server installation complete. Server JAR set to: ${SERVER_JAR}"
}

install_fabric() {
  print_info "Starting Fabric Minecraft server installation for ${MINECRAFT_VERSION}..."
  
  local fab_installer_ver=""
  if [ -z "${FABRIC_INSTALLER_VERSION}" ] || [ "${FABRIC_INSTALLER_VERSION}" == "latest" ]; then
    print_info "FABRIC_INSTALLER_VERSION set to 'latest' or empty. Auto-detecting..."
    local fabric_installer_api_url="https://meta.fabricmc.net/v2/versions/installer"
    local installer_json=$(curl -sSLf "$fabric_installer_api_url")
    if [ $? -ne 0 ] || [ -z "$installer_json" ]; then
      print_error "Failed to fetch Fabric installer versions from meta.fabricmc.net."
    fi
    fab_installer_ver=$(echo "$installer_json" | jq -r '.[0].version') # Get the very first (latest) installer
    if [ -z "$fab_installer_ver" ] || [ "$fab_installer_ver" == "null" ]; then
      print_error "Could not determine the latest Fabric Installer version. Please specify FABRIC_INSTALLER_VERSION manually."
    fi
    print_info "Resolved Fabric Installer Version to: ${fab_installer_ver}"
  else
    fab_installer_ver="${FABRIC_INSTALLER_VERSION}"
    print_info "Using specified Fabric Installer Version: ${fab_installer_ver}"
  fi

  local fabric_installer_url="https://maven.fabricmc.net/net/fabricmc/fabric-installer/${fab_installer_ver}/fabric-installer-${fab_installer_ver}.jar"

  print_info "Downloading Fabric installer (tool version ${fab_installer_ver})..."
  download_file "$fabric_installer_url" "${SERVER_DIR}/${INSTALLER_JAR_NAME}"

  # Resolve "latest" or "snapshot" for Fabric Loader version if specified
  local effective_modloader_version="${MODLOADER_VERSION}"
  if [ "${MODLOADER_VERSION}" == "latest" ] || [ "${MODLOADER_VERSION}" == "snapshot" ]; then
        print_info "MODLOADER_VERSION set to '${MODLOADER_VERSION}' for Fabric. Auto-detecting latest loader for MC ${MINECRAFT_VERSION}..."
        
        # Use the direct loader versions endpoint for the specific Minecraft version
        local fabric_loader_api_url="https://meta.fabricmc.net/v2/versions/loader/${MINECRAFT_VERSION}"
        local loader_json=$(curl -sSLf "$fabric_loader_api_url")
        if [ $? -ne 0 ] || [ -z "$loader_json" ] || [ "$loader_json" == "[]" ]; then
            print_error "Failed to fetch Fabric loader versions for Minecraft ${MINECRAFT_VERSION}."
        fi

        local stable_filter="true"
        if [ "${MODLOADER_VERSION}" == "snapshot" ]; then
            stable_filter="false"
        fi

        # Find the latest stable/snapshot loader version
        effective_modloader_version=$(echo "$loader_json" | jq -r --arg STABLE_FILTER "$stable_filter" \
            '[.[] | select(.loader.stable == ($STABLE_FILTER | fromjson)) | .loader.version] | first')
        
        if [ -z "$effective_modloader_version" ] || [ "$effective_modloader_version" == "null" ]; then
            print_error "Could not determine the latest Fabric Loader version (stable: ${stable_filter}) for Minecraft ${MINECRAFT_VERSION}. Please specify MODLOADER_VERSION manually or check available versions."
        fi
        print_info "Resolved Fabric Loader Version to: ${effective_modloader_version}"
    fi

  print_info "Running Fabric installer..."
  local fabric_cmd_args="server -mcversion ${MINECRAFT_VERSION} -downloadMinecraft -noprofile"
  if [ -n "${effective_modloader_version}" ]; then
    fabric_cmd_args="${fabric_cmd_args} -loader ${effective_modloader_version}"
    print_info "Using specific Fabric Loader version: ${effective_modloader_version}"
  else
    print_info "Using latest stable Fabric Loader version for ${MINECRAFT_VERSION} (determined by installer)."
  fi

  java -jar "${SERVER_DIR}/${INSTALLER_JAR_NAME}" ${fabric_cmd_args}
  if [ $? -ne 0 ]; then
    print_error "Fabric installer execution failed."
  fi

  if [ ! -f "${SERVER_DIR}/fabric-server-launch.jar" ]; then
    print_error "fabric-server-launch.jar not found after installation. Check Fabric installer output and versions."
  fi
  
  # Aligning with individual Fabric script's file renaming and properties file creation
  if [ -f "${SERVER_DIR}/server.jar" ]; then
    mv "${SERVER_DIR}/server.jar" "${SERVER_DIR}/minecraft-server.jar"
    print_info "Renamed server.jar to minecraft-server.jar"
  fi
  mv "${SERVER_DIR}/fabric-server-launch.jar" "${SERVER_DIR}/server.jar"
  print_info "Renamed fabric-server-launch.jar to server.jar"
  echo "serverJar=minecraft-server.jar" > "${SERVER_DIR}/fabric-server-launcher.properties"
  print_info "Created fabric-server-launcher.properties"

  export SERVER_JAR="server.jar"
  print_info "Fabric server installation complete. Server JAR set to: ${SERVER_JAR}"
  rm -f "${SERVER_DIR}/${INSTALLER_JAR_NAME}" # Clean up installer
}

# Add this helper function near the other helper functions
standardize_server_jar() {
    local source_jar="$1"
    if [ -f "${SERVER_DIR}/${source_jar}" ]; then
        mv "${SERVER_DIR}/${source_jar}" "${SERVER_DIR}/server.jar"
        print_info "Renamed ${source_jar} to server.jar"
        return 0
    fi
    return 1
}

install_forge() {
    print_info "Starting Forge Minecraft server installation for ${MINECRAFT_VERSION}..."
    local forge_promo_url="https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json"
    
    # Pre-installation cleanup as seen in individual Forge script
    print_info "Performing pre-installation cleanup for Forge..."
    rm -rf "${SERVER_DIR}/libraries/net/minecraftforge/forge"
    rm -f "${SERVER_DIR}/unix_args.txt"
    print_info "Cleanup complete."

    print_info "Fetching Forge promotions data..."
    local promo_json=$(curl -sSLf "$forge_promo_url")
    local forge_build_version=""
    
    # If MODLOADER_VERSION is specified, use it
    if [ -n "${MODLOADER_VERSION}" ] && [ "${MODLOADER_VERSION}" != "latest" ]; then
        if [[ "${MODLOADER_VERSION}" == "${MINECRAFT_VERSION}-"* ]]; then
            forge_build_version=$(echo "${MODLOADER_VERSION}" | sed "s/${MINECRAFT_VERSION}-//")
        else
            forge_build_version="${MODLOADER_VERSION}"
        fi
        print_info "Using specified Forge build version: ${forge_build_version} (from MODLOADER_VERSION)"
    else
        # Try to find version from promotions first
        if [ $? -eq 0 ] && [ -n "$promo_json" ]; then
            forge_build_version=$(echo "$promo_json" | jq -r --arg MC_VERSION "$MINECRAFT_VERSION" '.[$MC_VERSION + "-recommended"] // .[$MC_VERSION + "-latest"]')
        fi

        # If no version found in promotions, try to find the latest version from the Maven metadata
        if [ -z "$forge_build_version" ] || [ "$forge_build_version" == "null" ]; then
            print_info "No Forge version found in promotions, checking Maven metadata..."
            local maven_meta_url="https://maven.minecraftforge.net/net/minecraftforge/forge/maven-metadata.xml"
            local maven_data=$(curl -sSLf "$maven_meta_url")
            if [ $? -eq 0 ] && [ -n "$maven_data" ]; then
                # Extract versions matching our Minecraft version
                forge_build_version=$(echo "$maven_data" | grep -oP "${MINECRAFT_VERSION}-\K[0-9.]+" | tail -n1)
                if [ -n "$forge_build_version" ]; then
                    print_info "Found latest Forge build version from Maven: ${forge_build_version}"
                fi
            fi
        fi

        if [ -z "$forge_build_version" ] || [ "$forge_build_version" == "null" ]; then
            print_error "Could not automatically determine Forge build version for Minecraft ${MINECRAFT_VERSION}. Please specify MODLOADER_VERSION or ensure a recommended/latest version exists."
        fi
        print_info "Auto-detected Forge build version for ${MINECRAFT_VERSION}: ${forge_build_version}"
    fi

    local full_forge_version_string="${MINECRAFT_VERSION}-${forge_build_version}"
    local forge_installer_url="https://maven.minecraftforge.net/net/minecraftforge/forge/${full_forge_version_string}/forge-${full_forge_version_string}-installer.jar"

    print_info "Downloading Forge installer for ${full_forge_version_string}..."
    download_file "$forge_installer_url" "${SERVER_DIR}/${INSTALLER_JAR_NAME}"

    print_info "Running Forge installer..."
    java -jar "${SERVER_DIR}/${INSTALLER_JAR_NAME}" --installServer
    if [ $? -ne 0 ]; then
      print_error "Forge installer execution failed."
    fi

    # Look for and rename the shim jar
    local shim_jar=$(find "${SERVER_DIR}" -maxdepth 1 -name "forge-${MINECRAFT_VERSION}-*-shim.jar" ! -name "*installer*" -print -quit)
    if [ -n "$shim_jar" ]; then
        standardize_server_jar "$(basename "$shim_jar")"
        export SERVER_JAR="server.jar"
        print_info "Found and renamed Forge shim JAR to: server.jar"
    fi

    # Create unix_args.txt with proper format in home directory
    if [ -d "${SERVER_DIR}/libraries/net/minecraftforge/forge" ]; then
        local forge_version=$(ls "${SERVER_DIR}/libraries/net/minecraftforge/forge/" | head -n1)
        if [ -n "$forge_version" ]; then
            echo "@libraries/net/minecraftforge/forge/${forge_version}/unix_args.txt" > "${SERVER_DIR}/unix_args.txt"
            print_info "Created unix_args.txt with proper library path"
        fi
    fi

    # Update the post-installation handling section to prioritize run.sh
    if [ -f "${SERVER_DIR}/run.sh" ]; then
        print_info "Forge run.sh script found. Making it executable..."
        chmod +x "${SERVER_DIR}/run.sh"
        
        # Modern Forge uses forge-installer as the server jar
        if [ -f "${SERVER_DIR}/forge-installer.jar" ]; then
            mv "${SERVER_DIR}/forge-installer.jar" "${SERVER_DIR}/server.jar"
            print_info "Renamed forge-installer.jar to server.jar"
        fi
        
        # Ensure proper symlinks and file structure
        if [ -d "${SERVER_DIR}/libraries/net/minecraftforge/forge" ]; then
            print_info "Creating unix_args.txt symlink for modern Forge..."
            ln -sf "${SERVER_DIR}/libraries/net/minecraftforge/forge/"*"/unix_args.txt" "${SERVER_DIR}/unix_args.txt"
        fi
        
        export SERVER_JAR="server.jar" # Changed from "run.sh" to "server.jar"
        print_info "Server is configured to use server.jar for startup"
    else
        # Look for the server JAR in priority order
        local found_jar=false
        
        # First try to find the shim jar (newer Forge versions)
        local shim_jar=$(find "${SERVER_DIR}" -maxdepth 1 -name "forge-${MINECRAFT_VERSION}-*-shim.jar" ! -name "*installer*" -print -quit)
        if [ -n "$shim_jar" ]; then
            standardize_server_jar "$(basename "$shim_jar")"
            found_jar=true
        fi
        
        # Try to find the regular forge server jar if shim not found
        if [ "$found_jar" = false ]; then
            local forge_jar=$(find "${SERVER_DIR}" -maxdepth 1 -name "forge-${MINECRAFT_VERSION}-*-server.jar" ! -name "*installer*" -print -quit)
            if [ -n "$forge_jar" ]; then
                standardize_server_jar "$(basename "$forge_jar")"
                found_jar=true
            fi
        fi

        # Try universal jar as last resort
        if [ "$found_jar" = false ]; then
            local universal_jar=$(find "${SERVER_DIR}" -maxdepth 1 -name "forge-${MINECRAFT_VERSION}-*-universal.jar" ! -name "*installer*" -print -quit)
            if [ -n "$universal_jar" ]; then
                standardize_server_jar "$(basename "$universal_jar")"
                found_jar=true
            fi
        fi

        # If we found and renamed a JAR, use standard startup
        if [ "$found_jar" = true ]; then
            export SERVER_JAR="server.jar"
            print_info "Found and renamed Forge JAR to: server.jar"
        else
            # If we have user_jvm_args.txt, use that even without finding a specific JAR
            if [ -f "${SERVER_DIR}/user_jvm_args.txt" ]; then
                print_info "Using user_jvm_args.txt for startup configuration"
                export SERVER_JAR="AUTO_FORGE_NEOFORGE_SCRIPT"
            else
                print_error "Could not find any valid Forge server JAR files after installation"
            fi
        fi
    fi

    # Always create unix_args symlink for 1.17+ if not using run.sh
    if [[ $MINECRAFT_VERSION =~ ^1\.(17|18|19|20|21|22|23) ]]; then
        if [ -d "${SERVER_DIR}/libraries/net/minecraftforge/forge" ]; then
            print_info "Creating unix_args.txt symlink for modern Forge..."
            ln -sf "${SERVER_DIR}/libraries/net/minecraftforge/forge/"*"/unix_args.txt" "${SERVER_DIR}/unix_args.txt"
        fi
    fi

    print_info "Forge server installation complete."
    print_info "IMPORTANT: Use './run.sh' as your startup command in Pterodactyl."
    print_info "Alternative startup: 'java {SERVER_MEMORY} @user_jvm_args.txt @unix_args.txt nogui'"
    rm -f "${SERVER_DIR}/${INSTALLER_JAR_NAME}"
}

install_neoforge() {
  print_info "Starting NeoForge Minecraft server installation for ${MINECRAFT_VERSION}..."

  # Pre-installation cleanup
  print_info "Performing pre-installation cleanup for NeoForge..."
  rm -rf "${SERVER_DIR}/libraries/net/neoforged/neoforge" "${SERVER_DIR}/libraries/net/neoforged/forge"
  rm -f "${SERVER_DIR}/unix_args.txt"
  print_info "Cleanup complete."

  local effective_neoforge_version=""
  local artifact_name="neoforge"
  local maven_url="https://maven.neoforged.net/releases/net/neoforged"

  # Handle 1.20.1 specially as it uses the forge artifact name
  if [[ "${MINECRAFT_VERSION}" == "1.20.1" ]]; then
    artifact_name="forge"
    local xml_data=$(curl -sSLf "${maven_url}/forge/maven-metadata.xml" || echo "")
  else
    local xml_data=$(curl -sSLf "${maven_url}/neoforge/maven-metadata.xml" || echo "")
  fi

  if [ -n "${MODLOADER_VERSION}" ] && [ "${MODLOADER_VERSION}" != "latest" ]; then
    effective_neoforge_version="${MODLOADER_VERSION}"
    print_info "Using specified NeoForge version: ${effective_neoforge_version}"
  else
    if [ -n "$xml_data" ]; then
      if [[ "${MINECRAFT_VERSION}" == "1.20.1" ]]; then
        # 1.20.1 versions include the MC version
        version_key="${MINECRAFT_VERSION}-"
        effective_neoforge_version=$(echo "$xml_data" | grep -oP "<version>${version_key}[^<]+" | cut -d'>' -f2 | tail -n1)
      else
        # For newer versions, get version without MC prefix
        effective_neoforge_version=$(echo "$xml_data" | grep -oP "<version>[0-9.]+(-beta)?</version>" | grep -oP "[0-9.]+(-beta)?" | tail -n1)
      fi

      if [ -n "$effective_neoforge_version" ]; then
        print_info "Found NeoForge version from Maven metadata: ${effective_neoforge_version}"
      else
        print_error "No valid NeoForge version found for Minecraft ${MINECRAFT_VERSION}"
      fi
    else
      print_error "Could not fetch NeoForge version metadata. Server might be down."
    fi
  fi

  # Only add Minecraft version prefix for 1.20.1, not for newer versions
  local download_version
  if [[ "${MINECRAFT_VERSION}" == "1.20.1" ]]; then
    if [[ ! "$effective_neoforge_version" =~ ^${MINECRAFT_VERSION}- ]]; then
      download_version="${MINECRAFT_VERSION}-${effective_neoforge_version}"
    else
      download_version="${effective_neoforge_version}"
    fi
  else
    download_version="${effective_neoforge_version}"
  fi

  local installer_url="${maven_url}/${artifact_name}/${download_version}/${artifact_name}-${download_version}-installer.jar"
  
  print_info "Downloading NeoForge installer from ${installer_url}..."
  if ! download_file "$installer_url" "${SERVER_DIR}/${INSTALLER_JAR_NAME}"; then
    print_error "Failed to download NeoForge installer. This version may not exist or the server might be unavailable."
  fi

  print_info "Running NeoForge installer..."
  # Fixed installer command - removed --outputDir flag
  java -jar "${SERVER_DIR}/${INSTALLER_JAR_NAME}" installServer
  if [ $? -ne 0 ]; then
    print_error "NeoForge installer execution failed. Try increasing memory limits if using unlimited (0) value."
  fi

  # Create symlink for unix args
  print_info "Setting up NeoForge startup configuration..."
  ln -sf "${SERVER_DIR}/libraries/net/neoforged/${artifact_name}/"*/unix_args.txt "${SERVER_DIR}/unix_args.txt"
  
  # Handle post-installation file setup
  if [ -f "${SERVER_DIR}/run.sh" ]; then
    chmod +x "${SERVER_DIR}/run.sh"
    print_info "NeoForge run.sh script found and made executable."
  fi

  # Always use server.jar for NeoForge
  if [ -f "${SERVER_DIR}/${artifact_name}-server.jar" ]; then
    standardize_server_jar "${artifact_name}-server.jar"
  fi

  export SERVER_JAR="server.jar"
  print_info "Server will start using server.jar for startup."
  
  # Ensure we have the startup configuration
  if [ -f "${SERVER_DIR}/user_jvm_args.txt" ]; then
    print_info "Found user_jvm_args.txt for startup configuration."
  fi

  print_info "NeoForge server installation complete."
  rm -f "${SERVER_DIR}/${INSTALLER_JAR_NAME}"
}

# --- Main Script Logic ---
SECONDS=0 # Start timer

# Initial setup (apt, mkdir, cd) is handled by the "Basic Startup" block at the very top.

check_dependencies
check_env_vars # This now reliably resolves MINECRAFT_VERSION "latest" or "snapshot"

print_info "Starting installation in $(pwd)"

case "${MOD_LOADER_TYPE}" in
  vanilla)
    install_vanilla
    ;;
  fabric)
    install_fabric
    ;;
  forge)
    install_forge
    ;;
  neoforge)
    install_neoforge
    ;;
  *)
    print_error "Unsupported MOD_LOADER_TYPE: '${MOD_LOADER_TYPE}'. Supported types are 'vanilla', 'fabric', 'forge', 'neoforge'."
    ;;
esac

if [ ! -f "${JAVA_ARGS_FILE}" ] && ([ "${MOD_LOADER_TYPE}" == "vanilla" ] || [ "${MOD_LOADER_TYPE}" == "fabric" ]); then
  print_info "Creating default ${JAVA_ARGS_FILE} for custom JVM arguments..."
  echo "# Add custom Java arguments here, one per line (e.g., -XX:+UseG1GC)" > "${JAVA_ARGS_FILE}"
  echo "# These will be used if your Pterodactyl egg's startup command includes @${JAVA_ARGS_FILE##*/}" >> "${JAVA_ARGS_FILE}"
elif [ -f "${JAVA_ARGS_FILE}" ]; then
  print_info "${JAVA_ARGS_FILE} already exists (likely created by Forge/NeoForge installer)."
else
  print_info "Skipping default ${JAVA_ARGS_FILE} creation as it's not standard for ${MOD_LOADER_TYPE} or handled by its installer."
fi

# Create .serverjar file to specify which JAR to use for startup
if [ -n "${SERVER_JAR}" ]; then
  if [ "${SERVER_JAR}" == "AUTO_FORGE_NEOFORGE_SCRIPT" ]; then
    if [ -f "${SERVER_DIR}/run.sh" ]; then
      echo "run.sh" > "${SERVER_DIR}/.serverjar"
      print_info "Server will start using run.sh"
    elif [ -f "${SERVER_DIR}/server.jar" ]; then
      echo "server.jar" > "${SERVER_DIR}/.serverjar"
      print_info "Server will start using server.jar"
    else
      print_warning "No suitable server jar found for Forge/NeoForge. Server startup may fail."
    fi
  else
    echo "${SERVER_JAR}" > "${SERVER_DIR}/.serverjar"
    print_info "Server will start using ${SERVER_JAR}"
  fi
else
  print_warning "SERVER_JAR variable was not set. This is unexpected. Please check the script and installation logs."
fi

duration=$SECONDS
print_info "Minecraft server installation process finished in ${duration} seconds."

if [ -n "${SERVER_JAR}" ]; then
    if [ "${SERVER_JAR}" == "AUTO_FORGE_NEOFORGE_SCRIPT" ] || [ "${SERVER_JAR}" == "run.sh" ]; then
        print_info "Your startup command supports both run.sh and JAR-based execution."
        print_info "If startup fails, verify:"
        print_info "1. run.sh exists (for run.sh startup)"
        print_info "2. user_jvm_args.txt and unix_args.txt exist (for Forge/NeoForge)"
        print_info "3. server.jar exists (for vanilla/direct JAR startup)"
    else
        print_info "Server configured to use ${SERVER_JAR} for startup."
    fi
fi

if [ "${SERVER_JAR}" == "AUTO_FORGE_NEOFORGE_SCRIPT" ]; then
    if [ ! -f "${SERVER_DIR}/run.sh" ] && [ ! -f "${SERVER_DIR}/user_jvm_args.txt" ]; then
        print_warning "Critical startup files (run.sh or user_jvm_args.txt) were NOT found for ${MOD_LOADER_TYPE}. Server startup may fail."
    fi
fi

print_info "Installation script complete. Server files are in ${SERVER_DIR}."
exit 0
