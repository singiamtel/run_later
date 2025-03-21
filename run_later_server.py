#!/usr/bin/env python3

import argparse
import datetime
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path


class Task:
    def __init__(self, command, target_time, task_id=None, completed=False, exit_code=None, completion_time=None):
        self.command = command
        self.target_time = target_time
        self.task_id = task_id or str(int(time.time() * 1000))
        self.completed = completed
        self.exit_code = exit_code
        self.completion_time = completion_time
    
    def to_dict(self):
        data = {
            'command': self.command,
            'target_time': self.target_time.isoformat(),
            'task_id': self.task_id,
            'completed': self.completed
        }
        if self.exit_code is not None:
            data['exit_code'] = self.exit_code
        if self.completion_time:
            data['completion_time'] = self.completion_time.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data):
        task = cls(
            data['command'],
            datetime.datetime.fromisoformat(data['target_time']),
            data['task_id'],
            data.get('completed', False)
        )
        if 'exit_code' in data:
            task.exit_code = data['exit_code']
        if 'completion_time' in data:
            task.completion_time = datetime.datetime.fromisoformat(data['completion_time'])
        return task


class TaskServer:
    def __init__(self, socket_path):
        self.socket_path = socket_path
        self.tasks = {}  # Active tasks
        self.completed_tasks = {}  # Completed tasks
        self.lock = threading.Lock()
        self.running = True
        self.task_threads = {}
        self.tasks_file = self._get_tasks_file_path()
        self.completed_tasks_file = self._get_completed_tasks_file_path()
        self._load_tasks()
        self._load_completed_tasks()
    
    def _get_tasks_file_path(self):
        """Get the path to the persistent tasks file"""
        xdg_config_home = os.environ.get('XDG_CONFIG_HOME')
        if xdg_config_home:
            base_dir = os.path.join(xdg_config_home, 'run_later')
        else:
            base_dir = os.path.join(os.path.expanduser('~'), '.config', 'run_later')
        
        os.makedirs(base_dir, exist_ok=True)
        return os.path.join(base_dir, 'tasks.json')
    
    def _get_completed_tasks_file_path(self):
        """Get the path to the completed tasks file"""
        xdg_config_home = os.environ.get('XDG_CONFIG_HOME')
        if xdg_config_home:
            base_dir = os.path.join(xdg_config_home, 'run_later')
        else:
            base_dir = os.path.join(os.path.expanduser('~'), '.config', 'run_later')
        
        os.makedirs(base_dir, exist_ok=True)
        return os.path.join(base_dir, 'completed_tasks.json')
    
    def _load_tasks(self):
        """Load tasks from persistent storage"""
        if not os.path.exists(self.tasks_file):
            return
        
        try:
            with open(self.tasks_file, 'r') as f:
                tasks_data = json.load(f)
            
            for task_data in tasks_data.values():
                task = Task.from_dict(task_data)
                # Only load tasks that haven't expired yet
                if task.target_time > datetime.datetime.now():
                    self.tasks[task.task_id] = task
            
            print(f"Loaded {len(self.tasks)} tasks from {self.tasks_file}")
        except Exception as e:
            print(f"Error loading tasks: {e}")
    
    def _load_completed_tasks(self):
        """Load completed tasks from persistent storage"""
        if not os.path.exists(self.completed_tasks_file):
            return
        
        try:
            with open(self.completed_tasks_file, 'r') as f:
                tasks_data = json.load(f)
            
            for task_data in tasks_data.values():
                task = Task.from_dict(task_data)
                self.completed_tasks[task.task_id] = task
            
            # Keep only the last 100 completed tasks
            if len(self.completed_tasks) > 100:
                sorted_tasks = sorted(
                    self.completed_tasks.items(),
                    key=lambda x: x[1].completion_time or datetime.datetime.min,
                    reverse=True
                )
                self.completed_tasks = dict(sorted_tasks[:100])
            
            print(f"Loaded {len(self.completed_tasks)} completed tasks from {self.completed_tasks_file}")
        except Exception as e:
            print(f"Error loading completed tasks: {e}")
    
    def _save_tasks(self):
        """Save tasks to persistent storage"""
        try:
            tasks_data = {
                task_id: task.to_dict()
                for task_id, task in self.tasks.items()
            }
            
            with open(self.tasks_file, 'w') as f:
                json.dump(tasks_data, f, indent=2)
        except Exception as e:
            print(f"Error saving tasks: {e}")
    
    def _save_completed_tasks(self):
        """Save completed tasks to persistent storage"""
        try:
            tasks_data = {
                task_id: task.to_dict()
                for task_id, task in self.completed_tasks.items()
            }
            
            with open(self.completed_tasks_file, 'w') as f:
                json.dump(tasks_data, f, indent=2)
        except Exception as e:
            print(f"Error saving completed tasks: {e}")
    
    def start(self):
        # Create socket directory if it doesn't exist
        os.makedirs(os.path.dirname(self.socket_path), exist_ok=True)
        
        # Remove socket file if it exists
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(self.socket_path)
        self.server.listen(5)
        
        # Set socket permissions to allow all users to connect
        os.chmod(self.socket_path, 0o777)
        
        print(f"Server started at {self.socket_path}")
        
        # Start a thread to handle task execution
        self.scheduler_thread = threading.Thread(target=self.scheduler_loop)
        self.scheduler_thread.daemon = True
        self.scheduler_thread.start()
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)
        
        # Accept connections
        while self.running:
            try:
                self.server.settimeout(1.0)  # Set a timeout so we can check self.running periodically
                try:
                    client, _ = self.server.accept()
                    self.handle_client(client)
                except socket.timeout:
                    continue
            except Exception as e:
                if self.running:  # Only log errors if we're still running
                    print(f"Error in server loop: {e}")
    
    def handle_signal(self, signum, frame):
        print(f"\nReceived signal {signum}, shutting down gracefully...")
        self.stop()
    
    def scheduler_loop(self):
        """Background thread that checks for tasks to execute"""
        while self.running:
            now = datetime.datetime.now()
            tasks_to_run = []
            save_needed = False
            
            with self.lock:
                # Find tasks that are due
                for task_id, task in list(self.tasks.items()):
                    if task.target_time <= now:
                        tasks_to_run.append(task)
                        del self.tasks[task_id]
                        save_needed = True
            
            # Save tasks if any were removed
            if save_needed:
                self._save_tasks()
                
            # Run the tasks
            for task in tasks_to_run:
                self.execute_task(task)
            
            # Sleep for a short time before checking again
            time.sleep(1)
    
    def execute_task(self, task):
        """Execute a command in a separate thread"""
        thread = threading.Thread(
            target=self._run_command,
            args=(task.command, task.task_id)
        )
        thread.daemon = True
        
        with self.lock:
            self.task_threads[task.task_id] = thread
        
        thread.start()
    
    def _run_command(self, command, task_id):
        """Run a command and handle its output"""
        try:
            print(f"Executing task {task_id}: {command}")
            result = subprocess.run(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Log output to files in /tmp
            log_base = os.path.join(tempfile.gettempdir(), f"run_later_{task_id}")
            
            with open(f"{log_base}.stdout", "w") as f:
                f.write(result.stdout)
            
            with open(f"{log_base}.stderr", "w") as f:
                f.write(result.stderr)
            
            with open(f"{log_base}.exit", "w") as f:
                f.write(str(result.returncode))
            
            print(f"Task {task_id} completed with exit code {result.returncode}")
            print(f"Logs written to {log_base}.stdout and {log_base}.stderr")
            
            # Mark task as completed and save to history
            with self.lock:
                # Create a copy of the task for completed_tasks
                completion_time = datetime.datetime.now()
                completed_task = Task(
                    command=command,
                    target_time=completion_time - datetime.timedelta(seconds=1),  # Approximate target time
                    task_id=task_id,
                    completed=True,
                    exit_code=result.returncode,
                    completion_time=completion_time
                )
                self.completed_tasks[task_id] = completed_task
                
                # Limit the number of completed tasks we keep
                if len(self.completed_tasks) > 100:
                    # Sort by completion time and keep only the most recent 100
                    sorted_tasks = sorted(
                        self.completed_tasks.items(),
                        key=lambda x: x[1].completion_time or datetime.datetime.min,
                        reverse=True
                    )
                    self.completed_tasks = dict(sorted_tasks[:100])
                
                self._save_completed_tasks()
        
        except Exception as e:
            print(f"Error executing task {task_id}: {e}")
        
        finally:
            with self.lock:
                if task_id in self.task_threads:
                    del self.task_threads[task_id]
    
    def handle_client(self, client):
        try:
            # Receive message
            data = b""
            while True:
                chunk = client.recv(4096)
                if not chunk:
                    break
                data += chunk
            
            # Process message
            if data:
                message = json.loads(data.decode('utf-8'))
                response = self.process_message(message)
                
                # Send response
                client.sendall(json.dumps(response).encode('utf-8'))
        
        except Exception as e:
            print(f"Error handling client: {e}")
        
        finally:
            client.close()
    
    def process_message(self, message):
        """Process a message from a client"""
        action = message.get('action')
        
        if action == 'schedule':
            return self.handle_schedule(message)
        elif action == 'list':
            return self.handle_list()
        elif action == 'cancel':
            return self.handle_cancel(message)
        elif action == 'history':
            return self.handle_history(message)
        else:
            return {'status': 'error', 'message': f'Unknown action: {action}'}
    
    def handle_schedule(self, message):
        """Handle a request to schedule a task"""
        try:
            command = message.get('command')
            delay_seconds = message.get('delay_seconds')
            
            if not command or delay_seconds is None:
                return {'status': 'error', 'message': 'Missing command or delay'}
            
            target_time = datetime.datetime.now() + datetime.timedelta(seconds=delay_seconds)
            task = Task(command, target_time)
            
            with self.lock:
                self.tasks[task.task_id] = task
                self._save_tasks()
            
            return {
                'status': 'success',
                'message': 'Task scheduled',
                'task_id': task.task_id,
                'target_time': target_time.isoformat()
            }
        
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def handle_list(self):
        """Handle a request to list all scheduled tasks"""
        with self.lock:
            tasks_data = {
                task_id: task.to_dict()
                for task_id, task in self.tasks.items()
            }
        
        return {
            'status': 'success',
            'tasks': tasks_data
        }
    
    def handle_history(self, message):
        """Handle a request to list completed tasks"""
        limit = message.get('limit', 10)  # Default to last 10 tasks
        
        with self.lock:
            # Sort tasks by completion time, most recent first
            sorted_tasks = sorted(
                self.completed_tasks.items(),
                key=lambda x: x[1].completion_time or datetime.datetime.min,
                reverse=True
            )
            
            # Limit the number of tasks returned
            limited_tasks = sorted_tasks[:limit]
            
            tasks_data = {
                task_id: task.to_dict()
                for task_id, task in limited_tasks
            }
        
        return {
            'status': 'success',
            'tasks': tasks_data
        }
    
    def handle_cancel(self, message):
        """Handle a request to cancel a task"""
        task_id = message.get('task_id')
        
        if not task_id:
            return {'status': 'error', 'message': 'Missing task_id'}
        
        with self.lock:
            if task_id in self.tasks:
                del self.tasks[task_id]
                self._save_tasks()
                return {'status': 'success', 'message': f'Task {task_id} cancelled'}
            else:
                return {'status': 'error', 'message': f'Task {task_id} not found'}
    
    def stop(self):
        """Stop the server gracefully"""
        self.running = False
        
        # Wait for all task threads to complete (with a timeout)
        with self.lock:
            threads = list(self.task_threads.values())
        
        for thread in threads:
            thread.join(timeout=0.5)
        
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        
        print("Server stopped")


def get_server_socket_path():
    """Get the path to the server socket"""
    xdg_runtime_dir = os.environ.get('XDG_RUNTIME_DIR')
    
    if xdg_runtime_dir:
        base_dir = xdg_runtime_dir
    else:
        base_dir = os.path.join(tempfile.gettempdir(), f"run_later-{os.getuid()}")
    
    return os.path.join(base_dir, "run_later.sock")


def main():
    parser = argparse.ArgumentParser(description='Run Later Task Server')
    parser.add_argument('--socket', help='Unix socket path for the server')
    parser.add_argument('--daemon', action='store_true', help='Run as daemon (detach from terminal)')
    
    args = parser.parse_args()
    socket_path = args.socket or get_server_socket_path()
    
    # If running as daemon, redirect output to log file
    if args.daemon:
        log_file = os.path.expanduser('~/.local/share/run_later/server.log')
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        # Redirect stdout and stderr to log file
        sys.stdout = open(log_file, 'a')
        sys.stderr = sys.stdout
        
        # Log the start time
        print(f"\n--- Server started at {datetime.datetime.now().isoformat()} ---")
    
    server = TaskServer(socket_path)
    try:
        server.start()
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        server.stop()


if __name__ == '__main__':
    main() 