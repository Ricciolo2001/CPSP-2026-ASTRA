#pragma once
#include "cJSON.h"
#include <memory>
#include <string>
#include <string_view>

namespace cjson {

/// A cJSON element wrapper.
///
/// It manages the lifetime of a cJSON item, ensuring that it is properly freed
/// when the wrapper goes out of scope.
using Element = std::unique_ptr<cJSON, void (*)(cJSON *)>;

/// A JSON document/object.
///
/// The pointed-to cJSON object is owned by this wrapper and will be freed when
/// this object is destroyed.
class Document : public Element {
  public:
    Document() : Element(cJSON_CreateObject(), cJSON_Delete) {}

    /// Add a wrapped item to the object with the given key.
    void add(const char *key, Element item) {
        assert(get() != nullptr);
        assert(item != nullptr);
        // Note: cJSON_AddItemToObject takes ownership of the item, so we
        // release it from the wrapper
        cJSON_AddItemToObject(get(), key, item.release());
    }
    /// Add a wrapped item to the object with the given key.
    void add(const std::string &key, Element item) {
        add(key.c_str(), std::move(item));
    }

    /// Add a wrapped item to the object with the given key without transferring
    /// ownership.
    void addRef(const char *key, const Element &item) {
        assert(get() != nullptr);
        assert(item != nullptr);
        // Note: cJSON_AddItemToObject does NOT take ownership of the item, so
        // we do NOT release it from the wrapper
        cJSON_AddItemReferenceToObject(get(), key, item.get());
    }
    void addRef(const std::string &key, const Element &item) {
        addRef(key.c_str(), item);
    }
};

/// A JSON array.
///
/// The pointed-to cJSON array is owned by this wrapper and will be freed when
/// this object is destroyed.
class Arr : public Element {
  public:
    Arr() : Element(cJSON_CreateArray(), cJSON_Delete) {}

    /// Add a wrapped item to the array. Takes ownership from the wrapper.
    void addItem(Element item) {
        assert(get() != nullptr);
        assert(item != nullptr);
        // Note: cJSON_AddItemToArray takes ownership of the item, so we release
        // it from the wrapper
        cJSON_AddItemToArray(get(), item.release());
    }

    /// Add a wrapped item to the array without transferring ownership.
    void addItemRef(Element item) {
        assert(get() != nullptr);
        assert(item != nullptr);
        // Note: cJSON_AddItemToArray does NOT take ownership of the item, so we
        // do NOT release it from the wrapper
        cJSON_AddItemToArray(get(), item.get());
    }
};

/// An owning JSON string.
///
/// The pointed-to string is owned by this object and will be freed when this
/// object is destroyed.
class Str : public Element {
  public:
    explicit Str(const char *str)
        : Element(cJSON_CreateString(str), cJSON_Delete) {}

    explicit Str(std::string str) : Str(str.c_str()) {}

    explicit operator std::string_view() const {
        assert(get() != nullptr);
        return std::string_view(get()->valuestring);
    }
};

/// A non-owning JSON string reference.
///
/// The pointed-to string MUST outlive this object.
/// Use `cjson::Str` if you need ownership.
class StrRef : public Element {
  public:
    explicit StrRef(const char *str)
        : Element(cJSON_CreateStringReference(str), cJSON_Delete) {}

    explicit operator std::string_view() const {
        assert(get() != nullptr);
        return std::string_view(get()->valuestring);
    }
};

/// A JSON number.
class Num : public Element {
  public:
    explicit Num(double num) : Element(cJSON_CreateNumber(num), cJSON_Delete) {}
};

/// A JSON boolean.
class Bool : public Element {
  public:
    explicit Bool(bool value)
        : Element(cJSON_CreateBool(value), cJSON_Delete) {}
};

class Null : public Element {
  public:
    Null() : Element(cJSON_CreateNull(), cJSON_Delete) {}
};

/// A heap-allocated string returned by cJSON_Print or cJSON_PrintUnformatted.
///
/// The pointed-to string is owned by this object and will be freed when this
/// object is destroyed.
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

/// Print the JSON document without formatting (no newlines, no indentation).
///
/// The returned string is allocated on the heap and will be automatically freed
/// when the AllocatedStr goes out of scope.
inline AllocatedStr printUnformatted(const Element &doc) {
    assert(doc.get() != nullptr);
    return AllocatedStr{cJSON_PrintUnformatted(doc.get())};
}

/// Print the JSON document with formatting (newlines, indentation).
///
/// The returned string is allocated on the heap and will be automatically freed
/// when the AllocatedStr goes out of scope.
inline AllocatedStr print(const Element &doc) {
    assert(doc.get() != nullptr);
    return AllocatedStr{cJSON_Print(doc.get())};
}

} // namespace cjson
