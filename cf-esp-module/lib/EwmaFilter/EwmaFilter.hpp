#pragma once

/// An Exponentially Weighted Moving Average (EWMA) filter.
///
/// The filter maintains an exponentially weighted moving average of the samples
/// The `alpha` parameter controls the smoothing factor: higher alpha means more
/// weight on recent samples (more responsive, less smooth), while lower alpha
/// means more weight on older samples (smoother, less responsive).
template <typename T, typename InternalState = float> class EwmaFilter {
  public:
    /// Constructs an EwmaFilter with the given smoothing factor.
    ///
    /// @param alpha The smoothing factor in the range (0, 1]. Higher alpha
    /// means more weight on recent samples. A common default is 0.2.
    explicit EwmaFilter(InternalState alpha = InternalState{0.2})
        : alpha_(alpha) {
        assert(alpha > InternalState{0} && alpha <= InternalState{1});
    }

    /// Update the filter with a new sample and return the new filtered value.
    T update(T newSample);

    /// Get the current filtered value. Returns the smoothed average
    /// of all samples seen so far. If no samples have been seen, returns the
    /// default-constructed value of InternalState (e.g. 0.0 for float).
    [[nodiscard]] T get() const { return static_cast<T>(currentAverage_); }

    /// Reset the filter to its initial state, forgetting all past samples.
    void reset();

  private:
    InternalState alpha_;
    InternalState currentAverage_ = {};
    bool isFirstSample_ = true;
};

template <typename T, typename InternalState>
T EwmaFilter<T, InternalState>::update(T newSample) {
    if (isFirstSample_) {
        currentAverage_ = static_cast<InternalState>(newSample);
        isFirstSample_ = false;
    } else {
        currentAverage_ = alpha_ * static_cast<InternalState>(newSample) +
                          (InternalState{1} - alpha_) * currentAverage_;
    }
    return get();
}

template <typename T, typename InternalState>
void EwmaFilter<T, InternalState>::reset() {
    currentAverage_ = {};
    isFirstSample_ = true;
}
