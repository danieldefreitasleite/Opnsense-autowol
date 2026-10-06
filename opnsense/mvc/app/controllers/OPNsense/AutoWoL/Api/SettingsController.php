<?php

/*
 * Copyright (C) 2026 AutoWoL Project
 * All rights reserved.
 */

namespace OPNsense\AutoWoL\Api;

use OPNsense\Base\ApiMutableModelControllerBase;
use OPNsense\Core\Backend;
use OPNsense\Core\Config;

class SettingsController extends ApiMutableModelControllerBase
{
    protected static $internalModelName = 'autowol';
    protected static $internalModelClass = 'OPNsense\AutoWoL\AutoWoL';

    public function setAction()
    {
        $result = ['result' => 'failed'];
        if ($this->request->isPost()) {
            Config::getInstance()->lock();
            $mdl = $this->getModel();

            // Try getting payload with 'autowol' wrapper first
            $postData = $this->request->getPost(static::$internalModelName);
            if (empty($postData)) {
                // Fallback if form posted without prefix
                $postData = $this->request->getPost();
            }
            if (empty($postData)) {
                $raw = $this->request->getJsonRawBody(true);
                if (is_array($raw)) {
                    $postData = isset($raw[static::$internalModelName]) ? $raw[static::$internalModelName] : $raw;
                }
            }

            if (!empty($postData) && is_array($postData)) {
                $mdl->setNodes($postData);
            }

            $result = $this->validate();
            if (empty($result['validations'])) {
                $this->setActionHook();
                $saveResult = $this->save(false, true);

                // Automatically reconfigure template on save so autowol.cron and config are immediately updated
                try {
                    $backend = new Backend();
                    $backend->configdRun('template reload OPNsense/AutoWoL');
                } catch (\Exception $e) {
                    // Ignore if configd temporarily unavailable
                }

                return $saveResult;
            }
        }
        return $result;
    }
}
