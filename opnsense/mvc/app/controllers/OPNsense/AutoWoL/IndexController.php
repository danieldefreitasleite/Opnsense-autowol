<?php

/*
 * Copyright (C) 2026 AutoWoL Project
 * All rights reserved.
 */

namespace OPNsense\AutoWoL;

class IndexController extends \OPNsense\Base\IndexController
{
    public function indexAction()
    {
        $this->view->title = gettext("AutoWoL: Monitor de Hosts e Wake-on-LAN");
        $this->view->generalForm = $this->getForm("general");
        $this->view->dialogHost = $this->getForm("dialogHost");
        $this->view->notificationsForm = $this->getForm("notifications");
        $this->view->pick('OPNsense/AutoWoL/index');
    }
}
