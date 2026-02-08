#include <iostream>
#include <string>
#include <vector>

// Base class
class Base {
public:
    int base_value;
    
    Base(int val = 0) : base_value(val) {
        std::cout << "Base constructor: " << base_value << std::endl;
    }
    
    virtual ~Base() {
        std::cout << "Base destructor: " << base_value << std::endl;
    }
    
    virtual void print() const {
        std::cout << "Base::print() - base_value: " << base_value << std::endl;
    }
    
    virtual Base* clone() const {
        return new Base(*this);
    }
};

// Derived class
class Derived : public Base {
public:
    int derived_value;
    
    Derived(int base_val = 0, int derived_val = 0) 
        : Base(base_val), derived_value(derived_val) {
        std::cout << "Derived constructor: " << base_value 
                  << ", " << derived_value << std::endl;
    }
    
    ~Derived() {
        std::cout << "Derived destructor: " << base_value 
                  << ", " << derived_value << std::endl;
    }
    
    void print() const override {
        std::cout << "Derived::print() - base_value: " << base_value 
                  << ", derived_value: " << derived_value << std::endl;
    }
    
    Derived* clone() const override {
        return new Derived(*this);
    }
};

// Function that takes Base by value (causes slicing!)
void function_by_value(Base b) {
    std::cout << "\n--- Inside function_by_value ---" << std::endl;
    b.print();  // Will call Base::print(), not Derived::print()
    std::cout << "--- End function_by_value ---\n" << std::endl;
}

// Function that takes Base by reference (no slicing)
void function_by_reference(const Base& b) {
    std::cout << "\n--- Inside function_by_reference ---" << std::endl;
    b.print();  // Will call Derived::print() if b is actually a Derived
    std::cout << "--- End function_by_reference ---\n" << std::endl;
}

// Function that takes Base by pointer (no slicing)
void function_by_pointer(const Base* b) {
    std::cout << "\n--- Inside function_by_pointer ---" << std::endl;
    if (b) {
        b->print();  // Will call Derived::print() if b points to Derived
    }
    std::cout << "--- End function_by_pointer ---\n" << std::endl;
}

int main() {
    std::cout << "=== Demonstrating Object Slicing ===\n" << std::endl;
    
    // Create a derived object
    Derived derived(10, 20);
    
    std::cout << "\n1. Direct call on derived object:" << std::endl;
    derived.print();
    
    // ============================================
    // CASE 1: Assignment to base object (SLICING!)
    // ============================================
    std::cout << "\n2. Assignment to Base object (SLICING occurs):" << std::endl;
    Base base_obj = derived;  // Object slicing! Only Base part is copied
    base_obj.print();  // Calls Base::print(), derived_value is lost!
    
    // ============================================
    // CASE 2: Passing by value (SLICING!)
    // ============================================
    std::cout << "\n3. Passing Derived by value to function (SLICING occurs):" << std::endl;
    function_by_value(derived);  // Object slicing!
    
    // ============================================
    // CASE 3: Passing by reference (NO SLICING)
    // ============================================
    std::cout << "\n4. Passing Derived by reference (NO slicing):" << std::endl;
    function_by_reference(derived);  // No slicing, virtual dispatch works
    
    // ============================================
    // CASE 4: Passing by pointer (NO SLICING)
    // ============================================
    std::cout << "\n5. Passing Derived by pointer (NO slicing):" << std::endl;
    function_by_pointer(&derived);  // No slicing, virtual dispatch works
    
    // ============================================
    // CASE 5: Vector of base objects (SLICING!)
    // ============================================
    std::cout << "\n6. Storing Derived objects in vector<Base> (SLICING occurs):" << std::endl;
    std::vector<Base> vec;
    vec.push_back(derived);  // Object slicing! Only Base part stored
    vec[0].print();  // Calls Base::print()
    
    // ============================================
    // CASE 6: Vector of base pointers (NO SLICING)
    // ============================================
    std::cout << "\n7. Storing Derived pointers in vector<Base*> (NO slicing):" << std::endl;
    std::vector<Base*> vec_ptr;
    vec_ptr.push_back(new Derived(30, 40));
    vec_ptr[0]->print();  // Calls Derived::print()
    
    // Cleanup
    for (Base* ptr : vec_ptr) {
        delete ptr;
    }
    
    std::cout << "\n=== End of demonstration ===" << std::endl;
    
    return 0;
}
