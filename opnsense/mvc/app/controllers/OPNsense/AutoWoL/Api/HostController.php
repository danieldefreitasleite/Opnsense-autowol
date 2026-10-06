<?php

/*
 * Copyright (C) 2026 AutoWoL Project
 * All rights reserved.
 */

namespace OPNsense\AutoWoL\Api;

use OPNsense\Base\ApiMutableModelControllerBase;

class HostController extends ApiMutableModelControllerBase
{
    protected static $internalModelName = 'autowol';
    protected static $internalModelClass = 'OPNsense\AutoWoL\AutoWoL';

    public function searchHostAction()
    {
        return $this->searchBase('hosts.host', ['enabled', 'name', 'ip', 'mac', 'check_method', 'max_retries']);
    }

    public function getHostAction($uuid = null)
    {
        return $this->getBase('host', 'hosts.host', $uuid);
    }

    public function addHostAction()
    {
        return $this->addBase('host', 'hosts.host');
    }

    public function setHostAction($uuid)
    {
        return $this->setBase('host', 'hosts.host', $uuid);
    }

    public function delHostAction($uuid)
    {
        return $this->delBase('hosts.host', $uuid);
    }

    public function toggleHostAction($uuid)
    {
        return $this->toggleBase('hosts.host', $uuid);
    }
}
