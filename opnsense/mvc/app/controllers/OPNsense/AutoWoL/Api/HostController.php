<?php

/*
 * Copyright (C) 2026 AutoWoL Project
 * All rights reserved.
 */

namespace OPNsense\AutoWoL\Api;

use OPNsense\Base\ApiMutableModelControllerBase;
use OPNsense\Core\Backend;

class HostController extends ApiMutableModelControllerBase
{
    protected static $internalModelName = 'autowol';
    protected static $internalModelClass = 'OPNsense\AutoWoL\AutoWoL';

    private function reloadAutoWoL()
    {
        try {
            $backend = new Backend();
            $backend->configdRun('template reload OPNsense/AutoWoL');
        } catch (\Exception $e) {
            // Log or ignore if configd temporarily unavailable
        }
    }

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
        $res = $this->addBase('host', 'hosts.host');
        if (isset($res['result']) && $res['result'] === 'saved') {
            $this->reloadAutoWoL();
        }
        return $res;
    }

    public function setHostAction($uuid)
    {
        $res = $this->setBase('host', 'hosts.host', $uuid);
        if (isset($res['result']) && $res['result'] === 'saved') {
            $this->reloadAutoWoL();
        }
        return $res;
    }

    public function delHostAction($uuid)
    {
        $res = $this->delBase('hosts.host', $uuid);
        if (isset($res['result']) && $res['result'] === 'deleted') {
            $this->reloadAutoWoL();
        }
        return $res;
    }

    public function toggleHostAction($uuid, $enabled = null)
    {
        $res = $this->toggleBase('hosts.host', $uuid, $enabled);
        $this->reloadAutoWoL();
        return $res;
    }
}
