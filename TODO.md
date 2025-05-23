# **Automated Mod Validation (AMV): Simplified Development Timeline**

This timeline provides a high-level overview of the development phases for Automated Mod Validation (AMV), focusing on key milestones and the integration of the Discord bot.

## **Phase 1: Alpha \- Core Setup & Basic Connections**

* **Goal:** Get the foundational pieces in place and ensure basic communication between the system's components.

### **Alpha 1: Initial Setup & Orchestration**

* **Focus:** Choose your primary language (Python/Node.js), set up project structure, and create the central "brain" (Orchestration Engine) that will manage everything.  
* **Key Features:**  
  * Basic configuration loading (for settings like API keys).  
  * Initial logging.  
  * **Discord Bot Integration (Basic):** Get your Discord bot running and able to send a simple "AMV System Started\!" message to a designated channel.

### **Alpha 2: VM & Server Panel Control**

* **Focus:** Automate the creation, startup, and shutdown of your testing VMs (Proxmox) and game servers (Server Panel).  
* **Key Features:**  
  * Connect to Proxmox API: Clone, start, stop client VMs.  
  * Connect to Server Panel API: Create, start, stop, delete game servers.  
  * Basic SSH access to client VMs for command execution.

## **Phase 2: Beta \- First Automated Test Run**

* **Goal:** Execute a complete, automated test run for a single mod, from setup to result reporting.

### **Beta 1: Automated Minecraft Client & Server**

* **Focus:** Get Minecraft (client and server) to launch and perform basic actions automatically.  
* **Key Features:**  
  * Scripts within the client VM to install Minecraft/mod loader and launch the game.  
  * Basic in-game automation (e.g., movement, world creation) on the client.  
  * Server-side scripts to launch the modded server.  
  * **Discord Bot Integration (Notifications):** The bot sends "Test Run for \[Mod Name\] Started\!" and "Test Run for \[Mod Name\] Finished: \[Status\]" messages.

### **Beta 2: Full Test Flow & Data Collection**

* **Focus:** Orchestrate the client connecting to the server, perform simple combined tests, and collect essential data.  
* **Key Features:**  
  * Client VM automatically connects to the newly created server.  
  * Basic client-server interaction tests (e.g., joining, simple mod feature interaction).  
  * Automated collection of client and server logs.  
  * Automated detection and transfer of crash reports.

### **Beta 3: Reporting & Crash Report Sharing**

* **Focus:** Display test results on the web interface and make crash reports easily accessible.  
* **Key Features:**  
  * Reporting Service displays pass/fail status for each test run.  
  * Links to collected logs and crash reports on the reporting site.  
  * **Discord Bot Integration (Crash Reports):** The bot automatically uploads crash reports (or links to them) to Discord when a test fails.

## **Phase 3: Release Candidate (RC) \- Refinement & Usability**

* **Goal:** Make the system robust, easy to configure for new mods, and user-friendly.

### **RC 1: Robustness & Dynamic Configuration**

* **Focus:** Improve error handling and make it easy to add new mods to test without changing code.  
* **Key Features:**  
  * Better error handling and retry mechanisms for all API calls.  
  * Flexible configuration files to define new test profiles for different mods, Minecraft versions, and server types.

### **RC 2: Enhanced Reporting & Documentation**

* **Focus:** Improve the Reporting Service's user experience and provide clear instructions.  
* **Key Features:**  
  * Improved UI/UX for the Reporting Service (dashboards, filtering).  
  * Comprehensive documentation for setting up and using AMV.  
  * **Discord Bot Integration (Summary):** The bot can provide a brief summary of recent test results on demand or periodically.

## **V1.0 Launch\!**

* **Goal:** The first stable, fully functional release of Automated Mod Validation (AMV), ready for regular use.

## **Post-Launch: Ongoing Improvements**

* **Focus:** Adding advanced features like scheduled runs, more complex client automation, and performance monitoring.  
* **Key Features:**  
  * Scheduled test runs.  
  * Advanced in-game automation (e.g., pathfinding, inventory).  
  * Performance metrics (FPS, TPS, memory usage).  
  * Multi-client testing.