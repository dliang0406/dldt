﻿// Copyright (c) 2016 Intel Corporation
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.


#pragma once

#include "convolution_kernel_base.h"
#include <vector>

namespace kernel_selector {

class ConvolutionKernel_1x1_gemm_MMAD : public ConvolutionKernelBase {
public:
    using Parent = ConvolutionKernelBase;
    ConvolutionKernel_1x1_gemm_MMAD() : ConvolutionKernelBase("convolution_gpu_1x1_gemm_MMAD") {}
    virtual ~ConvolutionKernel_1x1_gemm_MMAD() {}

    KernelsData GetKernelsData(const Params& params, const optional_params& options) const override;
    ParamsKey GetSupportedKey() const override;

protected:
    JitConstants GetJitConstants(const convolution_params& params, const DispatchData& kd) const override;
    DispatchData SetDefault(const convolution_params& arg, int autoTuneIndex = -1) const override;
    bool Validate(const Params& p, const optional_params& o) const override;
    std::vector<WeightsLayout> GetSupportedWeightLayouts(const convolution_params&) const override {
        return {
            WeightsLayout::os_is_yx_isa8_osv8_isv4,
        };
    }
};
}  // namespace kernel_selector