#!/usr/bin/env python3

import argparse
import datetime
import json
import os
import re
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
    print("Starting run_later server daemon...")
    
    # Get the path to run_later_server.py
    script_dir = os.path.dirname(os.path.abspath(__file__))
    server_script = os.path.join(script_dir, "run_later_server.py")
    
    # Start server as a daemon
    subprocess.Popen(
        [sys.executable, server_script, "--socket", socket_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True
    )
    
    # Wait for server to start
    for _ in range(5):  # Try for up to 5 seconds
        if os.path.exists(socket_path):
            time.sleep(0.5)  # Give the server a moment to start accepting connections
            return True
        time.sleep(1)
    
    raise RuntimeError("Failed to start server")


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


def main():
    parser = argparse.ArgumentParser(description='Schedule commands to run later.')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Schedule command
    schedule_parser = subparsers.add_parser('schedule', help='Schedule a task')
    schedule_parser.add_argument('cmd', help='Command to run (enclose in quotes)')
    schedule_parser.add_argument('delay', help='Delay before running (e.g., "5 minutes", "1 hour")')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List scheduled tasks')
    
    # Cancel command
    cancel_parser = subparsers.add_parser('cancel', help='Cancel a scheduled task')
    cancel_parser.add_argument('task_id', help='ID of the task to cancel')
    
    args = parser.parse_args()
    
    socket_path = get_server_socket_path()
    
    if args.command == 'schedule':
        schedule_task(args.cmd, args.delay, socket_path)
    elif args.command == 'list':
        list_tasks(socket_path)
    elif args.command == 'cancel':
        cancel_task(args.task_id, socket_path)
    else:
        # If no command given and arguments are provided, assume it's a legacy style call
        if len(sys.argv) >= 3:
            schedule_task(sys.argv[1], sys.argv[2], socket_path)
        else:
            parser.print_help()
            sys.exit(1)


if __name__ == '__main__':
    main() 