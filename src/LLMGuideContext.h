#ifndef LLM_GUIDE_CONTEXT_H
#define LLM_GUIDE_CONTEXT_H

#include <string>
#include "Define.h"

class Player;

char const* GetGuideEquipmentSlotName(uint8 slot);

// Versioned, request-time snapshot. No Player pointer survives this call.
std::string BuildGuideSnapshot(Player* player, std::string const& summary);

#endif
