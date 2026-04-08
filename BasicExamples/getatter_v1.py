# dynamic_utils_demo.py

"""
📌 Demo: Dynamic attribute utilities in Python
This file shows how to use:
- hasattr: check if an object has an attribute
- getattr: get attribute value dynamically
- setattr: set or create attributes dynamically
- delattr: remove attributes dynamically
"""

# --- Sample Class ---
class Person:
    def __init__(self, name, age):
        self.name = name
        self.age = age

    def greet(self):
        return f"Hello, my name is {self.name} and I am {self.age} years old."

# --- Utility Functions ---
def print_attributes(obj):
    """Print all attributes of an object."""
    print(f"\nAttributes of {obj.__class__.__name__}:")
    for attr in dir(obj):
        # Skip private and built-in attributes
        if not attr.startswith("_"):
            value = getattr(obj, attr)
            print(f" - {attr}: {value}")

def safe_get(obj, attr, default=None):
    """Get attribute safely."""
    if hasattr(obj, attr):
        return getattr(obj, attr)
    return default

def add_or_update(obj, attr, value):
    """Add or update attribute dynamically."""
    setattr(obj, attr, value)
    print(f"Set '{attr}' = {value}")

def remove_attr(obj, attr):
    """Remove attribute if exists."""
    if hasattr(obj, attr):
        delattr(obj, attr)
        print(f"Removed attribute '{attr}'")
    else:
        print(f"Attribute '{attr}' not found, cannot remove.")

# --- Main Function ---
def main():
    # Create a Person instance
    p = Person("Alice", 30)

    # 1️⃣ Print existing attributes
    print_attributes(p)

    # 2️⃣ Check if an attribute exists
    if hasattr(p, "name"):
        print(f"\n✅ 'name' exists: {getattr(p, 'name')}")

    if not hasattr(p, "email"):
        print("\n❌ 'email' not found, adding it dynamically...")
        setattr(p, "email", "alice@example.com")

    # 3️⃣ Access attributes safely
    print(f"Email (safe_get): {safe_get(p, 'email')}")
    print(f"Phone (safe_get with default): {safe_get(p, 'phone', 'N/A')}")

    # 4️⃣ Update attribute dynamically
    add_or_update(p, "age", 31)

    # 5️⃣ Remove attribute dynamically
    remove_attr(p, "email")
    remove_attr(p, "phone")  # non-existent

    # 6️⃣ Final attribute state
    print_attributes(p)

    # 7️⃣ Call a method dynamically
    if hasattr(p, "greet"):
        greet_fn = getattr(p, "greet")
        print(f"\nCalling method dynamically: {greet_fn()}")

# --- Run main() only if script is executed directly ---
if __name__ == "__main__":
    main()