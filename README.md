# Run Later

A Unix task scheduler written in Python that allows running commands after a specified delay using a client/server architecture.

## Features

- Schedule commands to run after a time delay
- Client/server architecture - the command returns immediately while the task runs in the background
- Automatic server daemon management (starts when needed)
- List scheduled tasks
- Cancel scheduled tasks
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

# Cancel a scheduled task
./run_later cancel <task_id>
```

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

# Cancel a specific task
./run_later cancel 1682946573123
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
4. Task outputs are logged to the /tmp directory for later inspection

## Requirements

- Python 3.6 or higher 