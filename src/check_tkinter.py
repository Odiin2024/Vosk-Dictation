import tkinter as tk

# Try to create a basic window
try:
    root = tk.Tk()
    root.title("Tkinter Test")
    label = tk.Label(root, text="Tkinter is working!")
    label.pack(padx=20, pady=20)
    
    # Optional - close after 3 seconds
    root.after(3000, root.destroy)
    
    print("Tkinter is available on your system!")
    root.mainloop()
except Exception as e:
    print(f"Error importing or using tkinter: {e}")
