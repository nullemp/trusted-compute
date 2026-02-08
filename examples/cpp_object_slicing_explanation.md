# C++ Object Slicing: Derived-to-Base Conversion

## Key Concept

> "The automatic derived-to-base conversion applies only for conversions to a reference or pointer type. There is no such conversion from a derived-class type to the base-class type. Nevertheless, it is often possible to convert an object of a derived class to its base-class type. However, such conversions may not behave as we might want."

## What This Means

### ✅ Automatic Conversions (No Slicing)

C++ automatically converts derived types to base types when dealing with **references** or **pointers**:

```cpp
Derived d;
Base* ptr = &d;      // ✅ OK - pointer conversion
Base& ref = d;       // ✅ OK - reference conversion
```

These conversions preserve the full object and virtual function dispatch works correctly.

### ❌ Object Slicing (Problem!)

When you convert a derived object to a base object **by value**, object slicing occurs:

```cpp
Derived d;
Base b = d;          // ❌ SLICING! Only Base part is copied
```

The derived object is **copied** into a base object, but only the base-class portion is copied. The derived-class members are **lost**.

## Common Scenarios Where Slicing Occurs

1. **Direct Assignment**
   ```cpp
   Base b = derived_obj;  // Slicing!
   ```

2. **Passing by Value**
   ```cpp
   void func(Base b);  // Takes by value
   func(derived_obj);  // Slicing!
   ```

3. **Returning by Value**
   ```cpp
   Base func() {
       Derived d;
       return d;  // Slicing!
   }
   ```

4. **Storing in Containers**
   ```cpp
   std::vector<Base> vec;
   vec.push_back(derived_obj);  // Slicing!
   ```

## Solutions

### 1. Use References or Pointers

```cpp
void func(const Base& b);        // ✅ By reference
void func(const Base* b);         // ✅ By pointer
std::vector<Base*> vec;          // ✅ Vector of pointers
std::vector<std::unique_ptr<Base>> vec;  // ✅ Smart pointers
```

### 2. Use Virtual Functions

Virtual functions ensure the correct derived-class version is called even through base pointers/references:

```cpp
Base* ptr = new Derived();
ptr->virtual_function();  // Calls Derived::virtual_function()
```

### 3. Clone Pattern

If you need to copy polymorphic objects:

```cpp
class Base {
public:
    virtual Base* clone() const = 0;
};

class Derived : public Base {
public:
    Derived* clone() const override {
        return new Derived(*this);
    }
};
```

## Why This Matters

- **Lost Data**: Derived-class members are discarded
- **Wrong Behavior**: Virtual functions may not work as expected
- **Unexpected Results**: The object behaves like a Base, not a Derived

## Example Output

When you run `cpp_object_slicing.cpp`, you'll see:
- Base constructors/destructors being called
- Only Base::print() being called after slicing
- Derived::print() being called when using references/pointers

This demonstrates that slicing loses the derived-class information and behavior.
