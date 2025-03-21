#!/usr/bin/env python3

import argparse
import datetime
import glob
import json
import os
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time


def parse_time_string(time_str):
    """Parse a time string like '25 minutes' or '2 hours' into seconds."""
    time_str = time_str.lower().strip()
    
    # Match patterns like "2 minutes", "1 hour", "30 seconds"
    match = re.match(r'(\d+)\s+(second|seconds|minute|minutes|hour|hours)', time_str)
    if not match:
        raise ValueError(f"Invalid time format: {time_str}. Examples: '5 minutes', '1 hour', '30 seconds'")
    
    amount = int(match.group(1))
    unit = match.group(2)
    
    if unit.startswith('second'):
        return amount
    elif unit.startswith('minute'):
        return amount * 60
    elif unit.startswith('hour'):
        return amount * 3600
    
    raise ValueError(f"Unknown time unit: {unit}")


def get_server_socket_path():
    """Get the path to the server socket"""
    xdg_runtime_dir = os.environ.get('XDG_RUNTIME_DIR')
    
    if xdg_runtime_dir:
        base_dir = xdg_runtime_dir
    else:
        base_dir = os.path.join(tempfile.gettempdir(), f"run_later-{os.getuid()}")
    
    return os.path.join(base_dir, "run_later.sock")


def send_message_to_server(message, socket_path):
    """Send a message to the server and return the response"""
    if not os.path.exists(socket_path):
        raise ValueError(f"Server socket not found at {socket_path}. Is the server running?")
    
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    
    try:
        client.connect(socket_path)
        client.sendall(json.dumps(message).encode('utf-8'))
        client.shutdown(socket.SHUT_WR)  # Signal that we're done sending
        
        # Receive response
        data = b""
        while True:
            chunk = client.recv(4096)
            if not chunk:
                break
            data += chunk
        
        return json.loads(data.decode('utf-8')) if data else None
    
    finally:
        client.close()


def start_server(socket_path=None):
    """Start the server daemon"""
    if not socket_path:
        socket_path = get_server_socket_path()
    
    if os.path.exists(socket_path):
        try:
            # Test if server is responsive
            test_message = {'action': 'list'}
            send_message_to_server(test_message, socket_path)
            print("Server is already running.")
            return
        except:
            # Socket exists but server is not responding
            os.unlink(socket_path)
    
    print("Starting run_later server daemon...")
    
    # Get the path to run_later_server.py
    script_dir = os.path.dirname(os.path.abspath(__file__))
    server_script = os.path.join(script_dir, "run_later_server.py")
    
    # Start server as a daemon
    subprocess.Popen(
        [sys.executable, server_script, "--socket", socket_path, "--daemon"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True
    )
    
    # Wait for server to start
    for _ in range(5):  # Try for up to 5 seconds
        if os.path.exists(socket_path):
            time.sleep(0.5)  # Give the server a moment to start accepting connections
            try:
                # Test if server is responsive
                test_message = {'action': 'list'}
                send_message_to_server(test_message, socket_path)
                print("Server started successfully.")
                return
            except:
                continue
        time.sleep(1)
    
    print("Failed to start server. Check the logs at ~/.local/share/run_later/server.log")
    sys.exit(1)


def stop_server(socket_path=None):
    """Stop the server daemon"""
    if not socket_path:
        socket_path = get_server_socket_path()
    
    if not os.path.exists(socket_path):
        print("Server is not running.")
        return
    
    try:
        # Try to get the list of running tasks before stopping
        message = {'action': 'list'}
        response = send_message_to_server(message, socket_path)
        tasks = response.get('tasks', {}) if response and response['status'] == 'success' else {}
        
        if tasks:
            print(f"Warning: There are {len(tasks)} scheduled tasks that will be preserved.")
            print("These tasks will resume when the server is started again.")
    except:
        pass
    
    # Find the server process
    try:
        # Look for the Python process running run_later_server.py
        ps_output = subprocess.check_output(
            ["ps", "-ef"],
            text=True
        )
        
        for line in ps_output.split('\n'):
            if "run_later_server.py" in line and "--daemon" in line:
                pid = int(line.split()[1])
                try:
                    os.kill(pid, signal.SIGTERM)
                    print(f"Sent termination signal to server (PID: {pid})")
                except ProcessLookupError:
                    pass
    except subprocess.CalledProcessError:
        pass
    
    # Wait for the socket to be removed
    for _ in range(5):  # Try for up to 5 seconds
        if not os.path.exists(socket_path):
            print("Server stopped successfully.")
            return
        time.sleep(1)
    
    # If socket still exists, force remove it
    if os.path.exists(socket_path):
        try:
            os.unlink(socket_path)
        except:
            pass
    
    print("Server stopped.")


def restart_server(socket_path=None):
    """Restart the server daemon"""
    if not socket_path:
        socket_path = get_server_socket_path()
    
    print("Restarting server...")
    stop_server(socket_path)
    time.sleep(1)  # Give it a moment to fully stop
    start_server(socket_path)


def ensure_server_running(socket_path):
    """Check if the server is running, and start it if not"""
    if os.path.exists(socket_path):
        # Try to connect to check if it's responsive
        try:
            test_message = {'action': 'list'}
            send_message_to_server(test_message, socket_path)
            return True  # Server is running
        except:
            # Socket exists but server is not responding
            if os.path.exists(socket_path):
                os.unlink(socket_path)
    
    # Start the server
    start_server(socket_path)
    return True


def schedule_task(command, delay_str, socket_path=None):
    """Schedule a task with the server"""
    if not socket_path:
        socket_path = get_server_socket_path()
    
    try:
        delay_seconds = parse_time_string(delay_str)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    ensure_server_running(socket_path)
    
    message = {
        'action': 'schedule',
        'command': command,
        'delay_seconds': delay_seconds
    }
    
    try:
        response = send_message_to_server(message, socket_path)
        
        if response['status'] == 'success':
            target_time = datetime.datetime.fromisoformat(response['target_time'])
            current_time = datetime.datetime.now()
            
            print(f"Task scheduled successfully.")
            print(f"Task ID: {response['task_id']}")
            print(f"Current time: {current_time.strftime('%H:%M:%S')}")
            print(f"Will execute at: {target_time.strftime('%H:%M:%S')}")
            print(f"Command to run: {command}")
            print(f"\nTo view logs later: run_later logs {response['task_id']}")
        else:
            print(f"Error scheduling task: {response.get('message', 'Unknown error')}")
            sys.exit(1)
    
    except Exception as e:
        print(f"Error communicating with server: {e}")
        sys.exit(1)


def list_tasks(socket_path=None):
    """List all scheduled tasks"""
    if not socket_path:
        socket_path = get_server_socket_path()
    
    if not os.path.exists(socket_path):
        print("Server is not running. No tasks scheduled.")
        return
    
    message = {'action': 'list'}
    
    try:
        response = send_message_to_server(message, socket_path)
        
        if response['status'] == 'success':
            tasks = response.get('tasks', {})
            
            if not tasks:
                print("No tasks scheduled.")
                return
            
            print(f"Scheduled tasks ({len(tasks)}):")
            for task_id, task_data in tasks.items():
                target_time = datetime.datetime.fromisoformat(task_data['target_time'])
                command = task_data['command']
                
                # Truncate long commands
                if len(command) > 60:
                    command = command[:57] + "..."
                
                print(f"  - {task_id}: {target_time.strftime('%H:%M:%S')} - {command}")
        else:
            print(f"Error listing tasks: {response.get('message', 'Unknown error')}")
            sys.exit(1)
    
    except Exception as e:
        print(f"Error communicating with server: {e}")
        sys.exit(1)


def history(limit=10, socket_path=None):
    """List completed tasks"""
    if not socket_path:
        socket_path = get_server_socket_path()
    
    if not os.path.exists(socket_path):
        print("Server is not running. No task history available.")
        return
    
    message = {
        'action': 'history',
        'limit': limit
    }
    
    try:
        response = send_message_to_server(message, socket_path)
        
        if response['status'] == 'success':
            tasks = response.get('tasks', {})
            
            if not tasks:
                print("No completed tasks found.")
                return
            
            print(f"Recent completed tasks ({len(tasks)}):")
            for task_id, task_data in tasks.items():
                completion_time = datetime.datetime.fromisoformat(task_data.get('completion_time', task_data['target_time']))
                command = task_data['command']
                exit_code = task_data.get('exit_code', 'unknown')
                
                # Green for success, red for failure
                status_color = '\033[92m' if exit_code == 0 else '\033[91m'
                reset_color = '\033[0m'
                
                # Truncate long commands
                if len(command) > 50:
                    command = command[:47] + "..."
                
                print(f"  - {task_id}: {completion_time.strftime('%Y-%m-%d %H:%M:%S')} - {status_color}[exit: {exit_code}]{reset_color} {command}")
                print(f"    View logs: run_later logs {task_id}")
        else:
            print(f"Error getting task history: {response.get('message', 'Unknown error')}")
            sys.exit(1)
    
    except Exception as e:
        print(f"Error communicating with server: {e}")
        sys.exit(1)


def cancel_task(task_id, socket_path=None):
    """Cancel a scheduled task"""
    if not socket_path:
        socket_path = get_server_socket_path()
    
    if not os.path.exists(socket_path):
        print("Server is not running. No tasks to cancel.")
        return
    
    message = {
        'action': 'cancel',
        'task_id': task_id
    }
    
    try:
        response = send_message_to_server(message, socket_path)
        
        if response['status'] == 'success':
            print(f"Task {task_id} cancelled successfully.")
        else:
            print(f"Error cancelling task: {response.get('message', 'Unknown error')}")
            sys.exit(1)
    
    except Exception as e:
        print(f"Error communicating with server: {e}")
        sys.exit(1)


def view_logs(task_id):
    """View the logs for a specific task"""
    log_base = os.path.join(tempfile.gettempdir(), f"run_later_{task_id}")
    stdout_log = f"{log_base}.stdout"
    stderr_log = f"{log_base}.stderr"
    exit_code_log = f"{log_base}.exit"
    
    if not os.path.exists(stdout_log) and not os.path.exists(stderr_log):
        print(f"No logs found for task {task_id}")
        
        # Check if there are any logs that might match by partial ID
        all_logs = glob.glob(os.path.join(tempfile.gettempdir(), "run_later_*.stdout"))
        matching_logs = [log for log in all_logs if task_id in os.path.basename(log)]
        
        if matching_logs:
            print("Did you mean one of these tasks?")
            for log in matching_logs:
                log_id = os.path.basename(log).replace("run_later_", "").replace(".stdout", "")
                print(f"  {log_id}")
        return
    
    # Print exit code if available
    if os.path.exists(exit_code_log):
        with open(exit_code_log, 'r') as f:
            exit_code = f.read().strip()
            status_color = '\033[92m' if exit_code == '0' else '\033[91m'
            reset_color = '\033[0m'
            print(f"Task {task_id} completed with exit code: {status_color}{exit_code}{reset_color}")
    
    # Print stdout if available
    if os.path.exists(stdout_log):
        print("\n=== STDOUT ===")
        with open(stdout_log, 'r') as f:
            print(f.read())
    
    # Print stderr if available and not empty
    if os.path.exists(stderr_log):
        with open(stderr_log, 'r') as f:
            stderr_content = f.read()
            if stderr_content.strip():
                print("\n=== STDERR ===")
                print(stderr_content)


def get_server_info(socket_path=None):
    """Get detailed information about the server status and configuration"""
    if not socket_path:
        socket_path = get_server_socket_path()
    
    info = {
        'status': 'stopped',
        'pid': None,
        'socket_path': socket_path,
        'config_dir': os.path.expanduser('~/.config/run_later'),
        'log_dir': os.path.expanduser('~/.local/share/run_later'),
        'temp_dir': tempfile.gettempdir(),
        'tasks_file': os.path.expanduser('~/.config/run_later/tasks.json'),
        'history_file': os.path.expanduser('~/.config/run_later/completed_tasks.json'),
        'log_file': os.path.expanduser('~/.local/share/run_later/server.log'),
        'active_tasks': 0,
        'completed_tasks': 0,
        'uptime': None,
        'start_time': None
    }
    
    # Check if server is running and get PID
    try:
        ps_output = subprocess.check_output(
            ["ps", "-ef"],
            text=True
        )
        
        for line in ps_output.split('\n'):
            if "run_later_server.py" in line and "--daemon" in line:
                info['status'] = 'running'
                info['pid'] = int(line.split()[1])
                
                # Get process start time if possible
                try:
                    proc_stat = os.stat(f"/proc/{info['pid']}")
                    start_time = datetime.datetime.fromtimestamp(proc_stat.st_ctime)
                    info['start_time'] = start_time.isoformat()
                    info['uptime'] = str(datetime.datetime.now() - start_time)
                except:
                    pass
                break
    except subprocess.CalledProcessError:
        pass
    
    # If server is running, get task counts
    if info['status'] == 'running' and os.path.exists(socket_path):
        try:
            # Get active tasks
            message = {'action': 'list'}
            response = send_message_to_server(message, socket_path)
            if response and response['status'] == 'success':
                info['active_tasks'] = len(response.get('tasks', {}))
            
            # Get completed tasks count
            message = {'action': 'history', 'limit': 1000}  # Large limit to get total count
            response = send_message_to_server(message, socket_path)
            if response and response['status'] == 'success':
                info['completed_tasks'] = len(response.get('tasks', {}))
        except:
            pass
    
    # Check if files exist
    info['config_exists'] = os.path.exists(info['config_dir'])
    info['log_dir_exists'] = os.path.exists(info['log_dir'])
    info['tasks_file_exists'] = os.path.exists(info['tasks_file'])
    info['history_file_exists'] = os.path.exists(info['history_file'])
    info['log_file_exists'] = os.path.exists(info['log_file'])
    
    # Get log file size if it exists
    if info['log_file_exists']:
        info['log_file_size'] = os.path.getsize(info['log_file'])
    
    return info


def display_server_info(socket_path=None):
    """Display detailed information about the server"""
    info = get_server_info(socket_path)
    
    # Status with color
    status_color = '\033[92m' if info['status'] == 'running' else '\033[91m'
    reset_color = '\033[0m'
    
    print(f"\nServer Status: {status_color}{info['status'].upper()}{reset_color}")
    
    if info['status'] == 'running':
        print(f"Process ID: {info['pid']}")
        if info['start_time']:
            print(f"Start Time: {info['start_time']}")
        if info['uptime']:
            print(f"Uptime: {info['uptime']}")
        print(f"Active Tasks: {info['active_tasks']}")
        print(f"Completed Tasks: {info['completed_tasks']}")
    
    print("\nPaths:")
    print(f"Socket: {info['socket_path']}")
    print(f"Config Directory: {info['config_dir']}")
    print(f"Log Directory: {info['log_dir']}")
    print(f"Temporary Files: {info['temp_dir']}")
    
    print("\nFiles:")
    print(f"Tasks Database: {info['tasks_file']}" + 
          (" (exists)" if info['tasks_file_exists'] else " (not found)"))
    print(f"History Database: {info['history_file']}" + 
          (" (exists)" if info['history_file_exists'] else " (not found)"))
    print(f"Server Log: {info['log_file']}" + 
          (f" ({info['log_file_size']/1024:.1f} KB)" if info.get('log_file_size') else " (not found)"))
    
    print("\nQuick Commands:")
    print("  View tasks:    run_later list")
    print("  View history:  run_later history")
    print("  View logs:     tail -f " + info['log_file'])
    print("  Restart:       run_later server restart")


def main():
    parser = argparse.ArgumentParser(description='Schedule commands to run later.')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Schedule command
    schedule_parser = subparsers.add_parser('schedule', help='Schedule a task')
    schedule_parser.add_argument('cmd', help='Command to run (enclose in quotes)')
    schedule_parser.add_argument('delay', help='Delay before running (e.g., "5 minutes", "1 hour")')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List scheduled tasks')
    
    # History command
    history_parser = subparsers.add_parser('history', help='Show recently completed tasks')
    history_parser.add_argument('-n', '--limit', type=int, default=10, help='Number of tasks to show (default: 10)')
    
    # Cancel command
    cancel_parser = subparsers.add_parser('cancel', help='Cancel a scheduled task')
    cancel_parser.add_argument('task_id', help='ID of the task to cancel')
    
    # Logs command
    logs_parser = subparsers.add_parser('logs', help='View logs for a task')
    logs_parser.add_argument('task_id', help='ID of the task to view logs for')
    
    # Server management commands
    server_start_parser = subparsers.add_parser('server', help='Server management commands')
    server_subparsers = server_start_parser.add_subparsers(dest='server_command', help='Server command')
    
    start_parser = server_subparsers.add_parser('start', help='Start the server daemon')
    stop_parser = server_subparsers.add_parser('stop', help='Stop the server daemon')
    restart_parser = server_subparsers.add_parser('restart', help='Restart the server daemon')
    info_parser = server_subparsers.add_parser('info', help='Show server status and configuration')
    
    args = parser.parse_args()
    
    socket_path = get_server_socket_path()
    
    if args.command == 'server':
        if args.server_command == 'start':
            start_server(socket_path)
        elif args.server_command == 'stop':
            stop_server(socket_path)
        elif args.server_command == 'restart':
            restart_server(socket_path)
        elif args.server_command == 'info':
            display_server_info(socket_path)
        else:
            server_start_parser.print_help()
            sys.exit(1)
    elif args.command == 'schedule':
        schedule_task(args.cmd, args.delay, socket_path)
    elif args.command == 'list':
        list_tasks(socket_path)
    elif args.command == 'history':
        history(args.limit, socket_path)
    elif args.command == 'cancel':
        cancel_task(args.task_id, socket_path)
    elif args.command == 'logs':
        view_logs(args.task_id)
    else:
        # If no command given and arguments are provided, assume it's a legacy style call
        if len(sys.argv) >= 3:
            schedule_task(sys.argv[1], sys.argv[2], socket_path)
        else:
            parser.print_help()
            sys.exit(1)


if __name__ == '__main__':
    main() 