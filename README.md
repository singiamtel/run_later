# Run Later

A Unix task scheduler written in Python that allows running commands after a specified delay using a client/server architecture.

## Features

- Schedule commands to run after a time delay
- Client/server architecture - the command returns immediately while the task runs in the background
- Automatic server daemon management (starts when needed)
- List scheduled tasks
- Cancel scheduled tasks
- View task logs with detailed output
- View history of completed tasks with status
- Manual server control (start/stop/restart)
- Server status and configuration information
- Persistent tasks (survives server restarts and system reboots)
- Logs task outputs to /tmp directory

## Installation

1. Clone this repository
2. Make the scripts executable: `chmod +x run_later run_later_client.py run_later_server.py`
3. Add the script to your PATH (optional)

   ```bash
   # Add this line to your ~/.bashrc or ~/.zshrc
   export PATH=$PATH:/path/to/run_later
   ```

## Usage

### Basic Usage

```bash
# Run a command after a delay
./run_later 'command to run' 'time delay'
```

### Advanced Usage

```bash
# Schedule a task
./run_later schedule 'command to run' 'time delay'

# List all scheduled tasks
./run_later list

# View history of recently completed tasks
./run_later history

# Show more completed tasks (default is 10)
./run_later history -n 20

# Cancel a scheduled task
./run_later cancel <task_id>

# View task logs
./run_later logs <task_id>
```

### Server Management

```bash
# Start the server daemon
./run_later server start

# Stop the server daemon (tasks will be preserved)
./run_later server stop

# Restart the server daemon
./run_later server restart

# Show server status and configuration
./run_later server info
```

The `server info` command displays:
- Server status (running/stopped) and PID
- Server uptime and start time
- Number of active and completed tasks
- All configuration paths and files
- Log file locations and sizes
- Quick commands for common operations

### Examples

```bash
# Run a git commit and create a PR after 25 minutes
./run_later 'git commit --amend --reset-author && gh pr create -f' '25 minutes'

# Run a backup script after 1 hour
./run_later './backup.sh' '1 hour' 

# Run a notification after 30 seconds
./run_later 'echo "Time is up!"' '30 seconds'

# List all scheduled tasks
./run_later list

# View history of last 15 completed tasks
./run_later history -n 15

# Cancel a specific task
./run_later cancel 1682946573123

# View logs for a completed task
./run_later logs 1682946573123

# Check server status and configuration
./run_later server info

# Restart the server (tasks are preserved)
./run_later server restart
```

### Supported Time Formats

- Seconds: `30 seconds`, `1 second`
- Minutes: `5 minutes`, `1 minute`
- Hours: `2 hours`, `1 hour`

## How It Works

The system uses a client/server architecture:

1. The client (`run_later_client.py`) sends commands to the server
2. The server (`run_later_server.py`) runs as a background daemon and executes tasks at the scheduled time
3. The server automatically starts when needed and persists between commands
4. Tasks are saved to disk and will survive server restarts and system reboots
5. Task outputs are logged to the /tmp directory for later inspection
6. Logs can be viewed using the `logs` command
7. History of completed tasks is maintained and can be viewed with the `history` command
8. Server can be manually controlled with `server start/stop/restart` commands
9. Server status and configuration can be inspected with `server info`

## Files and Locations

- Socket: `/tmp/run_later-$UID/run_later.sock` or `$XDG_RUNTIME_DIR/run_later.sock`
- Tasks database: `~/.config/run_later/tasks.json`
- Completed tasks history: `~/.config/run_later/completed_tasks.json`
- Server logs: `~/.local/share/run_later/server.log`
- Task output logs: `/tmp/run_later_<task_id>.[stdout|stderr|exit]`

## Requirements

- Python 3.6 or higher 

## TO DO

- Support for days and weeks in time delay
    - Support for singular/plural (e.g. 1 day vs 2 days)
- Support for recurring tasks
- What happens when the server was down when a task was supposed to run?
- Add tests
