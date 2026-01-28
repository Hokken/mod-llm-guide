/*
 * Copyright (C) 2024+ AzerothCore <www.azerothcore.org>
 * Released under GNU AGPL v3 license: https://github.com/azerothcore/azerothcore-wotlk/blob/master/LICENSE-AGPL3
 */

#ifndef _LLM_GUIDE_CONFIG_H_
#define _LLM_GUIDE_CONFIG_H_

#include "Define.h"
#include <string>

class LLMGuideConfig
{
public:
    static LLMGuideConfig* instance();

    void LoadConfig();

    bool IsEnabled() const { return _enabled; }
    uint32 GetCooldownSeconds() const { return _cooldownSeconds; }
    uint32 GetPollIntervalMs() const { return _pollIntervalMs; }
    uint32 GetMaxResponseLength() const { return _maxResponseLength; }
    uint32 GetMaxPendingPerPlayer() const { return _maxPendingPerPlayer; }

private:
    LLMGuideConfig() = default;
    ~LLMGuideConfig() = default;

    bool _enabled = false;
    uint32 _cooldownSeconds = 10;
    uint32 _pollIntervalMs = 1000;
    uint32 _maxResponseLength = 800;
    uint32 _maxPendingPerPlayer = 3;
};

#define sLLMGuideConfig LLMGuideConfig::instance()

#endif // _LLM_GUIDE_CONFIG_H_
