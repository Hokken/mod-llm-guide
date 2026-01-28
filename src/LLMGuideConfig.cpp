/*
 * Copyright (C) 2024+ AzerothCore <www.azerothcore.org>
 * Released under GNU AGPL v3 license: https://github.com/azerothcore/azerothcore-wotlk/blob/master/LICENSE-AGPL3
 */

#include "LLMGuideConfig.h"
#include "Config.h"
#include "Log.h"

LLMGuideConfig* LLMGuideConfig::instance()
{
    static LLMGuideConfig instance;
    return &instance;
}

void LLMGuideConfig::LoadConfig()
{
    _enabled = sConfigMgr->GetOption<bool>("LLMGuide.Enable", false);
    _cooldownSeconds = sConfigMgr->GetOption<uint32>("LLMGuide.CooldownSeconds", 10);
    _pollIntervalMs = sConfigMgr->GetOption<uint32>("LLMGuide.PollIntervalMs", 1000);
    _maxResponseLength = sConfigMgr->GetOption<uint32>("LLMGuide.MaxResponseLength", 800);
    _maxPendingPerPlayer = sConfigMgr->GetOption<uint32>("LLMGuide.MaxPendingPerPlayer", 3);

    if (_enabled)
    {
        LOG_INFO("module", ">> LLM Guide module loaded");
        LOG_INFO("module", "   Cooldown: {} seconds", _cooldownSeconds);
        LOG_INFO("module", "   Poll interval: {} ms", _pollIntervalMs);
    }
    else
    {
        LOG_INFO("module", ">> LLM Guide module is disabled");
    }
}
