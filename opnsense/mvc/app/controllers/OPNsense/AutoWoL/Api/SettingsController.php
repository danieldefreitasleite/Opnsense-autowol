<?php

/*
 * Copyright (C) 2026 AutoWoL Project
 * All rights reserved.
 */

namespace OPNsense\AutoWoL\Api;

use OPNsense\Base\ApiMutableModelControllerBase;

class SettingsController extends ApiMutableModelControllerBase
{
    protected static $internalModelName = 'autowol';
    protected static $internalModelClass = 'OPNsense\AutoWoL\AutoWoL';
}
