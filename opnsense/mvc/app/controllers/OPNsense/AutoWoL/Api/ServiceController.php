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
        $backend = new Backend();
        $host = '';

        if (!empty($hostId)) {
            $host = $hostId;
        }

        if (empty($host) && $this->request->isPost()) {
            if ($this->request->hasPost('host')) {
                $host = $this->request->getPost('host');
            } elseif ($this->request->has('host')) {
                $host = $this->request->get('host');
            } else {
                $json = $this->request->getJsonRawBody(true);
                if (is_array($json) && !empty($json['host'])) {
                    $host = $json['host'];
                }
            }
        }

        if (empty($host)) {
            $host = $this->request->get('host', 'string', '');
        }

        $host = trim($host);
        if (empty($host)) {
            return ['status' => 'failed', 'response' => 'Erro: Identificador ou nome da máquina não foi fornecido.'];
        }

        $hostHex = bin2hex($host);
        $response = trim($backend->configdRun("autowol wake {$hostHex}"));
        return ['status' => 'ok', 'response' => $response ?: "Pacote WoL enviado para {$host}."];
    }

    public function statusAction()
    {
        $backend = new Backend();
        $response = $backend->configdRun('autowol status');
        $data = json_decode($response, true);
        if (!is_array($data)) {
            $data = [];
        }

        $cronActive = false;
        $cronSchedule = '';
        $cronFile = '/usr/local/etc/cron.d/autowol.cron';
        if (file_exists($cronFile)) {
            $cronContent = file_get_contents($cronFile);
            if (strpos($cronContent, 'autowol.py') !== false) {
                $cronActive = true;
                if (preg_match('/(\*\/[0-9]+|\*)\s+\*\s+\*\s+\*\s+\*/', $cronContent, $m)) {
                    $cronSchedule = $m[0];
                }
            }
        }

        return [
            'status' => 'ok',
            'data' => $data,
            'cron_active' => $cronActive,
            'cron_schedule' => $cronSchedule
        ];
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
