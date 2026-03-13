#pragma once
#include "cJSON.h"
#include <memory>
#include <string>
#include <string_view>

namespace cjson {

// Base alias to keep the code dry
using Element = std::unique_ptr<cJSON, decltype(&cJSON_Delete)>;

/// @brief A JSON document/object.
class Document : public Element {
  public:
    Document() : Element(cJSON_CreateObject(), cJSON_Delete) {}

    // Helper to add items to this object
    void add(const char *key, Element item) {
        assert(get() != nullptr);
        assert(item != nullptr);
        // Note: cJSON_AddItemToObject takes ownership of the item, so we
        // release it from the wrapper
        cJSON_AddItemToObject(get(), key, item.release());
    }
};

/// @brief A JSON array.
class Arr : public Element {
  public:
    Arr() : Element(cJSON_CreateArray(), cJSON_Delete) {}

    /// @brief Add a wrapped item to the array.
    /// Takes ownership from the wrapper.
    void addItem(Element item) {
        assert(get() != nullptr);
        assert(item != nullptr);
        // Note: cJSON_AddItemToArray takes ownership of the item, so we release
        // it from the wrapper
        cJSON_AddItemToArray(get(), item.release());
    }
};

/// @brief A JSON string.
class Str : public Element {
  public:
    explicit Str(std::string_view str)
        // Note: cJSON_CreateString makes a copy of the input string
        : Element(cJSON_CreateString(std::string(str).c_str()), cJSON_Delete) {}

    explicit Str(const char *str)
        : Element(cJSON_CreateString(str), cJSON_Delete) {}

    explicit operator std::string_view() const {
        assert(get() != nullptr);
        return std::string_view(get()->valuestring);
    }
};

class Num : public Element {
  public:
    explicit Num(double num) : Element(cJSON_CreateNumber(num), cJSON_Delete) {}
};

class Bool : public Element {
  public:
    explicit Bool(bool value)
        : Element(cJSON_CreateBool(value), cJSON_Delete) {}
};

class AllocatedStr : public std::unique_ptr<char, decltype(&cJSON_free)> {
  public:
    explicit AllocatedStr(char *str)
        : std::unique_ptr<char, decltype(&cJSON_free)>(str, cJSON_free) {}

    /// Allow explicit coversion to std::string_view for easy printing, etc.
    /// Internally string_view constructor calls ::length
    explicit operator std::string_view() const {
        assert(get() != nullptr);
        return std::string_view(get());
    }
};

inline AllocatedStr printUnformatted(const Document &doc) {
    assert(doc.get() != nullptr);
    return AllocatedStr{cJSON_PrintUnformatted(doc.get())};
}

inline AllocatedStr printUnformatted(const Arr &arr) {
    assert(arr.get() != nullptr);
    return AllocatedStr{cJSON_PrintUnformatted(arr.get())};
}

inline AllocatedStr printUnformatted(const Str &str) {
    assert(str.get() != nullptr);
    return AllocatedStr{cJSON_PrintUnformatted(str.get())};
}

} // namespace cjson
