import multiprocessing
import os
import time
import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
from functools import partial
from multiprocessing import Manager


# --- 1. Define the Function to be Parallelized ---
def cpu_intensive_task(number, log_queue):
    """
    A simple, CPU-bound function that logs its status to a queue.
    Logs 'STARTED' and 'FINISHED' messages in real-time.
    """
    pid = os.getpid()
    process_name = multiprocessing.current_process().name

    # Log when the task STARTS
    start_msg = f"[{process_name} (PID: {pid})] 🟢 STARTED value: {number}"
    log_queue.put(start_msg)

    # Simulate a calculation-heavy task
    result = 0
    # Using 500,000 iterations for quicker GUI demonstration
    for i in range(1, 500000):
        result += (number ** 0.5) / i

    # Log when the task FINISHES
    end_msg = f"[{process_name} (PID: {pid})] 🛑 FINISHED value: {number} | Result: {result:.4f}"
    log_queue.put(end_msg)

    return True


# --- 2. GUI Application Class ---
class MultiCoreApp:
    def __init__(self, master):
        self.master = master
        master.title("Python MultiCore Launcher (Summary Status)")
        master.geometry("800x600")  # Default size set to 800x600

        self.num_cores = os.cpu_count()
        self.is_running = False
        self.running_tasks = 0

        # FIX: Use Manager for safe cross-process sharing of the queue
        self.manager = Manager()
        self.log_queue = self.manager.Queue()

        # Dictionary to hold logs, grouped by worker name
        self.worker_logs = {}

        # --- Setup UI Elements ---
        self.status_var = tk.StringVar(value="Ready to start.")
        ttk.Label(master, textvariable=self.status_var, font=('Arial', 10, 'bold')).pack(pady=10)

        ttk.Label(master, text=f"Available Cores: {self.num_cores}").pack()

        self.launch_button = ttk.Button(master, text="🚀 Launch Parallel Calculation",
                                        command=self.start_calculation_thread)
        self.launch_button.pack(pady=10)

        self.progress = ttk.Progressbar(master, orient='horizontal', mode='indeterminate', length=400)
        self.progress.pack(pady=10)

        # 4. Output Log (ScrolledText)
        ttk.Label(master, text="--- Worker Summary Status ---").pack()
        self.log_area = scrolledtext.ScrolledText(master, width=90, height=25, state='disabled')
        self.log_area.pack(padx=10, pady=5)

        self.log_message(f"✅ System detected {self.num_cores} cores. Ready.", is_worker_log=False)

        # Ensure manager is shut down when the GUI closes
        master.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        """Called when the user closes the window."""
        self.manager.shutdown()
        self.master.destroy()

    def parse_worker_message(self, message):
        """Extracts the worker name block from the message (e.g., '[ForkPoolWorker-1 (PID: 1234)]')."""
        try:
            end_bracket = message.find(']')
            if message.startswith('['):
                return message[:end_bracket + 1]
        except:
            pass
        return "System/Control"

    def display_grouped_logs(self):
        """Renders the summary view: only the last message for each worker."""
        self.log_area.config(state='normal')
        self.log_area.delete('1.0', tk.END)

        output_text = ""

        # Display System messages first
        system_messages = self.worker_logs.get("System/Control", [])
        output_text += "--- System Messages ---\n"
        for msg in system_messages:
            output_text += msg + "\n"
        output_text += "\n--- Worker Summary Status ---\n"

        # Get worker groups, excluding System messages
        worker_group_names = [k for k in self.worker_logs.keys() if k != "System/Control"]

        for worker_name in sorted(worker_group_names):
            messages = self.worker_logs[worker_name]

            # 🌟 CORE LOGIC: Retrieve and display only the LAST message
            if messages:
                last_msg = messages[-1]

                # Remove the worker name from the individual message line for clean display
                cleaned_msg = last_msg[len(worker_name) + 1:]

                # Format the line as Worker Name : Status
                output_text += f"🤖 {worker_name}: {cleaned_msg}\n"

        self.log_area.insert(tk.END, output_text)
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

    def log_message(self, message, is_worker_log=True):
        """Stores the message in the appropriate group."""
        if is_worker_log:
            worker_name = self.parse_worker_message(message)
            if worker_name not in self.worker_logs:
                self.worker_logs[worker_name] = []

            # The worker only sends STARTED and FINISHED. We replace the STARTED with FINISHED.
            # This ensures only the final status is ever in the log list
            if message not in self.worker_logs[worker_name]:
                # If the message is FINISHED, replace the STARTED message if it exists
                if "FINISHED" in message and self.worker_logs[worker_name] and "STARTED" in \
                        self.worker_logs[worker_name][-1]:
                    self.worker_logs[worker_name][-1] = message
                else:
                    self.worker_logs[worker_name].append(message)

        else:
            # Non-worker messages go to the System/Control group
            system_name = "System/Control"
            if system_name not in self.worker_logs:
                self.worker_logs[system_name] = []
            if message not in self.worker_logs[system_name]:
                self.worker_logs[system_name].append(message)

    def start_calculation_thread(self):
        """Starts the main calculation logic in a separate thread."""
        if self.is_running:
            self.log_message("⚠️ Calculation already running.", is_worker_log=False)
            self.display_grouped_logs()
            return

        self.is_running = True
        self.running_tasks = 0

        # Clear logs from previous run
        self.worker_logs = {}
        self.display_grouped_logs()

        self.launch_button.config(state='disabled')
        self.progress.start(10)

        # Start the background thread for the heavy calculation and the thread for processing the queue
        threading.Thread(target=self.run_multicore_calculation, daemon=True).start()
        threading.Thread(target=self.process_queue, daemon=True).start()

    def run_multicore_calculation(self):
        """The main logic for multiprocessing.Pool using apply_async."""
        self.status_var.set("Submitting tasks in parallel...")
        self.log_message("--- Starting Pool.apply_async() ---", is_worker_log=False)
        self.display_grouped_logs()

        # Reduced input list (50 tasks) for quick UI demonstration
        data_inputs = list(range(1, 51))
        start_time = time.time()
        results_futures = []

        try:
            with multiprocessing.Pool(processes=self.num_cores) as pool:
                task_func = partial(cpu_intensive_task, log_queue=self.log_queue)

                for number in data_inputs:
                    res = pool.apply_async(task_func, args=(number,))
                    results_futures.append(res)
                    self.running_tasks += 1

                # Wait for all tasks to complete
                for future in results_futures:
                    future.get()
                    self.running_tasks -= 1

            end_time = time.time()
            elapsed = end_time - start_time

            self.log_queue.put(None)  # Send termination signal

            self.status_var.set(f"Finished in {elapsed:.4f} seconds!")
            self.log_message("✅ All tasks completed.", is_worker_log=False)
            self.log_message(f"🚀 Total calculation time: {elapsed:.4f} seconds.", is_worker_log=False)

        except Exception as e:
            self.status_var.set("An error occurred.")
            self.log_message(f"Error: {e}", is_worker_log=False)
            self.log_queue.put(None)

        finally:
            self.progress.stop()
            self.launch_button.config(state='normal')
            self.is_running = False
            self.master.after(0, self.display_grouped_logs)  # Final refresh

    def process_queue(self):
        """Continuously checks the queue, stores the log, and updates the grouped display."""
        while True:
            # Blocks until a message is received (or None is sent)
            message = self.log_queue.get()

            if message is None:
                break

            # Store the message (safe on the main thread)
            self.master.after(0, lambda m=message: self.log_message(m))
            # Refresh the display with the new summary line
            self.master.after(10, self.display_grouped_logs)

        self.log_message("Queue processing finished.", is_worker_log=False)
        self.master.after(0, self.display_grouped_logs)

    # --- 3. Main Execution Block for the GUI ---


if __name__ == '__main__':
    # Fixes for cross-platform multiprocessing stability in a GUI environment
    multiprocessing.freeze_support()
    multiprocessing.set_start_method('spawn', force=True)

    root = tk.Tk()
    app = MultiCoreApp(root)
    root.mainloop()