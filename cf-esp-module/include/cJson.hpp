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
class Element {
  public:
    explicit Element(cJSON *ptr) : element_(ptr, cJSON_Delete) {}

    Element(Element &&) = default;
    Element &operator=(Element &&) = default;

    // Non-copyable.
    Element(const Element &) = delete;
    Element &operator=(const Element &) = delete;

    /// Get the raw cJSON pointer. Useful for passing to cJSON functions.
    cJSON *get() const { return element_.get(); }

    /// Release ownership of the cJSON pointer.
    /// The caller is responsible for freeing it.
    cJSON *release() { return element_.release(); }

  private:
    std::unique_ptr<cJSON, void (*)(cJSON *)> element_;
};

/// A JSON document/object.
///
/// The pointed-to cJSON object is owned by this wrapper and will be freed when
/// this object is destroyed.
class Document : public Element {
  public:
    Document() : Element(cJSON_CreateObject()) {}

    /// Add a wrapped item to the object with the given key.
    void add(const char *key, Element item) {
        assert(get() != nullptr);
        assert(item.get() != nullptr);
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
        assert(item.get() != nullptr);
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
    Arr() : Element(cJSON_CreateArray()) {}

    /// Add a wrapped item to the array. Takes ownership from the wrapper.
    void addItem(Element item) {
        assert(get() != nullptr);
        assert(item.get() != nullptr);
        // Note: cJSON_AddItemToArray takes ownership of the item, so we release
        // it from the wrapper
        cJSON_AddItemToArray(get(), item.release());
    }

    /// Add a wrapped item to the array without transferring ownership.
    void addItemRef(const Element &item) {
        assert(get() != nullptr);
        assert(item.get() != nullptr);
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
    explicit Str(const char *str) : Element(cJSON_CreateString(str)) {}

    explicit Str(std::string_view str) : Str(str.data()) {}

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
        : Element(cJSON_CreateStringReference(str)) {}

    explicit operator std::string_view() const {
        assert(get() != nullptr);
        return std::string_view(get()->valuestring);
    }
};

/// A JSON number.
class Num : public Element {
  public:
    explicit Num(double num) : Element(cJSON_CreateNumber(num)) {}
};

/// A JSON boolean.
class Bool : public Element {
  public:
    explicit Bool(bool value) : Element(cJSON_CreateBool(value)) {}
};

/// A JSON null value.
class Null : public Element {
  public:
    Null() : Element(cJSON_CreateNull()) {}
};

/// A heap-allocated string returned by cJSON_Print or cJSON_PrintUnformatted.
///
/// The pointed-to string is owned by this object and will be freed when this
/// object is destroyed.
class AllocatedStr {
  public:
    explicit AllocatedStr(char *str) : str_(str, cJSON_free) {}

    explicit operator std::string_view() const {
        return std::string_view(str_.get());
    }

  private:
    std::unique_ptr<char, decltype(&cJSON_free)> str_;
};

/// Print the JSON document without formatting (no newlines, no indentation).
///
/// The returned string is allocated on the heap and will be automatically freed
/// when the AllocatedStr goes out of scope.
inline AllocatedStr printUnformatted(const Element &doc) {
    assert(doc.get() != nullptr);
    char *str = cJSON_PrintUnformatted(doc.get());
    if (!str) {
        throw std::runtime_error("Failed to print JSON document");
    }
    return AllocatedStr{str};
}

/// Print the JSON document with formatting (newlines, indentation).
///
/// The returned string is allocated on the heap and will be automatically freed
/// when the AllocatedStr goes out of scope.
inline AllocatedStr print(const Element &doc) {
    assert(doc.get() != nullptr);
    char *str = cJSON_Print(doc.get());
    assert(str != nullptr && "cJSON_Print failed to allocate string");
    return AllocatedStr{str};
}

} // namespace cjson
