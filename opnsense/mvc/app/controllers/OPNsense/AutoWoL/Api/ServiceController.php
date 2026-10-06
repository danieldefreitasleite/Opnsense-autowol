<?php

/*
 * Copyright (C) 2026 AutoWoL Project
 * All rights reserved.
 */

namespace OPNsense\AutoWoL\Api;

use OPNsense\Base\ApiControllerBase;
use OPNsense\Core\Backend;

class ServiceController extends ApiControllerBase
{
    public function reconfigureAction()
    {
        if ($this->request->isPost()) {
            $backend = new Backend();
            $backend->configdRun('template reload OPNsense/AutoWoL');
            $response = trim($backend->configdRun('autowol reconfigure'));
            return ['status' => 'ok', 'response' => $response];
        }
        return ['status' => 'failed'];
    }

    public function checkAction()
    {
        $backend = new Backend();
        $response = $backend->configdRun('autowol check');
        $data = json_decode($response, true);
        return ['status' => 'ok', 'data' => $data ?: $response];
    }

    public function wakeAction($hostId = '')
    {
        if ($this->request->isPost()) {
            $backend = new Backend();
            $host = $this->request->getPost('host', 'string', $hostId);
            $response = $backend->configdRun("autowol wake {$host}");
            return ['status' => 'ok', 'response' => $response];
        }
        return ['status' => 'failed'];
    }

    public function statusAction()
    {
        $backend = new Backend();
        $response = $backend->configdRun('autowol status');
        $data = json_decode($response, true);
        if (!is_array($data)) {
            $data = [];
        }
        return ['status' => 'ok', 'data' => $data];
    }

    public function logsAction()
    {
        $backend = new Backend();
        $response = $backend->configdRun('autowol logs');
        return ['status' => 'ok', 'logs' => $response ?: "Nenhum log registrado ainda."];
    }

    public function clearLogsAction()
    {
        if ($this->request->isPost()) {
            $backend = new Backend();
            $backend->configdRun('autowol clearlogs');
            return ['status' => 'ok', 'message' => 'Logs limpos com sucesso.'];
        }
        return ['status' => 'failed'];
    }

    public function testAlertAction($channel = 'all')
    {
        if ($this->request->isPost()) {
            $backend = new Backend();
            $targetChannel = $this->request->getPost('channel', 'string', $channel);
            $response = $backend->configdRun("autowol testalert {$targetChannel}");
            $data = json_decode($response, true);
            return ['status' => 'ok', 'result' => $data ?: $response];
        }
        return ['status' => 'failed'];
    }
}
