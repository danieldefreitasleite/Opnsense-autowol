{#
 # Copyright (C) 2026 AutoWoL Project
 # All rights reserved.
 #}

<script>
    $(document).ready(function() {
        var logTimer = null;

        // Carrega dados das configurações gerais e notificações
        mapDataToFormUI({'frm_general_settings': "/api/autowol/settings/get"});
        mapDataToFormUI({'frm_notifications': "/api/autowol/settings/get"});

        // Inicializa o BootGrid de Hosts
        $("#grid-hosts").UIBootgrid({
            search:'/api/autowol/host/searchHost',
            get:'/api/autowol/host/getHost/',
            set:'/api/autowol/host/setHost/',
            add:'/api/autowol/host/addHost/',
            del:'/api/autowol/host/delHost/',
            toggle:'/api/autowol/host/toggleHost/',
            options: {
                formatters: {
                    "commands": function (column, row) {
                        return "<button type=\"button\" class=\"btn btn-xs btn-default command-wake\" data-row-id=\"" + row.uuid + "\" data-row-name=\"" + row.name + "\" title=\"Ligar Agora (WoL)\"><span class=\"fa fa-power-off text-success\"></span></button> " +
                               "<button type=\"button\" class=\"btn btn-xs btn-default command-edit bootgrid-tooltip\" data-row-id=\"" + row.uuid + "\"><span class=\"fa fa-pencil\"></span></button> " +
                               "<button type=\"button\" class=\"btn btn-xs btn-default command-delete bootgrid-tooltip\" data-row-id=\"" + row.uuid + "\"><span class=\"fa fa-trash-o\"></span></button>";
                    }
                }
            }
        }).on("loaded.rs.jquery.bootgrid", function() {
            // Ação do botão "Ligar Agora (WoL)"
            $("#grid-hosts").find(".command-wake").on("click", function(e) {
                var hostName = $(this).data("row-name");
                var hostId = $(this).data("row-id");
                BootstrapDialog.confirm({
                    title: "{{ lang._('Wake-on-LAN') }}",
                    message: "{{ lang._('Deseja enviar o pacote Wake-on-LAN para: ') }}<strong>" + hostName + "</strong>?",
                    type: BootstrapDialog.TYPE_INFO,
                    btnOKLabel: "{{ lang._('Enviar WoL') }}",
                    btnCancelLabel: "{{ lang._('Cancelar') }}",
                    callback: function(result) {
                        if (result) {
                            ajaxCall("/api/autowol/service/wake", {'host': hostId || hostName}, function(data, status) {
                                BootstrapDialog.show({
                                    title: "{{ lang._('Resultado WoL') }}",
                                    message: data.response || "{{ lang._('Pacote enviado com sucesso!') }}",
                                    buttons: [{
                                        label: "{{ lang._('Fechar') }}",
                                        action: function(dialog) { dialog.close(); loadStatus(); loadLogs(); }
                                    }]
                                });
                            });
                        }
                    }
                });
            });
        });

        // Salvar Configurações Gerais
        $("#btn_save_general").click(function() {
            saveFormToEndpoint("/api/autowol/settings/set", 'frm_general_settings', function() {
                $("#btn_apply").addClass("btn-danger").removeClass("btn-primary");
            });
        });

        // Salvar Configurações de Notificações
        $("#btn_save_notifications").click(function() {
            saveFormToEndpoint("/api/autowol/settings/set", 'frm_notifications', function() {
                $("#btn_apply").addClass("btn-danger").removeClass("btn-primary");
            });
        });

        // Botão Aplicar Mudanças (Reconfigura templates e cron automaticamente)
        $("#btn_apply").click(function() {
            $("#btn_apply_icon").addClass("fa-spin");
            ajaxCall("/api/autowol/service/reconfigure", {}, function(data, status) {
                $("#btn_apply_icon").removeClass("fa-spin");
                $("#btn_apply").removeClass("btn-danger").addClass("btn-primary");
                BootstrapDialog.show({
                    title: "{{ lang._('AutoWoL Aplicado') }}",
                    message: "{{ lang._('Configurações salvas e cron do sistema reconfigurado com sucesso!') }}",
                    type: BootstrapDialog.TYPE_SUCCESS,
                    buttons: [{
                        label: "{{ lang._('OK') }}",
                        action: function(dialog) { dialog.close(); loadLogs(); }
                    }]
                });
            });
        });

        // Botão Checar Agora
        $("#btn_check_now").click(function() {
            $("#btn_check_icon").addClass("fa-spin");
            ajaxCall("/api/autowol/service/check", {}, function(data, status) {
                $("#btn_check_icon").removeClass("fa-spin");
                loadStatus();
                loadLogs();
                BootstrapDialog.show({
                    title: "{{ lang._('Checagem Executada') }}",
                    message: "<p>{{ lang._('Verificação concluída. Consulte os detalhes na aba Status e nos Logs.') }}</p>",
                    buttons: [{
                        label: "{{ lang._('Fechar') }}",
                        action: function(dialog) { dialog.close(); }
                    }]
                });
            });
        });

        // Testar Alertas
        $(".btn-test-alert").click(function() {
            var channel = $(this).data("channel");
            ajaxCall("/api/autowol/service/testAlert", {'channel': channel}, function(data, status) {
                loadLogs();
                BootstrapDialog.show({
                    title: "{{ lang._('Resultado do Teste de Alerta') }} (" + channel + ")",
                    message: "<pre>" + JSON.stringify(data.result, null, 2) + "</pre>",
                    buttons: [{
                        label: "{{ lang._('Fechar') }}",
                        action: function(dialog) { dialog.close(); }
                    }]
                });
            });
        });

        // Carrega aba de status em tempo real (Array de hosts formatado)
        function loadStatus() {
            ajaxCall("/api/autowol/service/status", {}, function(data, status) {
                if (data.data && Array.isArray(data.data)) {
                    if (data.data.length === 0) {
                        $("#status_container").html(
                            "<div class='alert alert-warning'>" +
                            "<i class='fa fa-exclamation-triangle'></i> {{ lang._('Nenhuma máquina cadastrada ainda. Adicione seus computadores na aba Máquinas / Servidores.') }}" +
                            "</div>"
                        );
                        return;
                    }

                    var html = "<table class='table table-striped table-hover table-bordered'><thead><tr>" +
                               "<th>{{ lang._('Máquina') }}</th>" +
                               "<th>{{ lang._('IP') }}</th>" +
                               "<th>{{ lang._('MAC') }}</th>" +
                               "<th>{{ lang._('Método') }}</th>" +
                               "<th style='width: 140px;'>{{ lang._('Status') }}</th>" +
                               "<th>{{ lang._('Tentativas WoL') }}</th>" +
                               "<th>{{ lang._('Última Vez Online') }}</th>" +
                               "<th>{{ lang._('Diagnóstico / Último Teste') }}</th>" +
                               "<th style='width: 80px;'>{{ lang._('Ações') }}</th>" +
                               "</tr></thead><tbody>";

                    data.data.forEach(function(item) {
                        var badge = "label-default";
                        var statusLabel = item.status || "NÃO CHECADO";
                        if (item.status === "ONLINE") {
                            badge = "label-success";
                            statusLabel = "🟢 ONLINE";
                        } else if (item.status === "WAKING") {
                            badge = "label-warning";
                            statusLabel = "🟡 LIGANDO (WoL)";
                        } else if (item.status === "ALERTED") {
                            badge = "label-danger";
                            statusLabel = "🔴 INOPERANTE";
                        } else if (item.status === "NOT_CHECKED") {
                            badge = "label-info";
                            statusLabel = "⚪ AGUARDANDO CRON";
                        }

                        var maxRetries = item.max_retries || 3;
                        var attemptsText = (item.attempts || 0) + " / " + maxRetries;

                        html += "<tr>";
                        html += "<td><strong>" + (item.name || "N/A") + "</strong></td>";
                        html += "<td><code>" + (item.ip || "N/A") + "</code></td>";
                        html += "<td><code>" + (item.mac || "N/A") + "</code></td>";
                        html += "<td><span class='label label-default'>" + (item.check_method || "icmp").toUpperCase() + "</span></td>";
                        html += "<td><span class='label " + badge + "' style='font-size: 11px; padding: 4px 8px;'>" + statusLabel + "</span></td>";
                        html += "<td>" + attemptsText + "</td>";
                        html += "<td>" + (item.last_seen_online || "Ainda não detectado") + "</td>";
                        html += "<td><small>" + (item.last_details || "Aguardando verificação") + "</small></td>";
                        html += "<td><button type='button' class='btn btn-xs btn-success status-wake-btn' data-id='" + item.id + "' data-name='" + item.name + "' title='Ligar agora com WoL'><i class='fa fa-power-off'></i> WoL</button></td>";
                        html += "</tr>";
                    });

                    html += "</tbody></table>";
                    $("#status_container").html(html);

                    $(".status-wake-btn").click(function() {
                        var hName = $(this).data("name");
                        var hId = $(this).data("id");
                        ajaxCall("/api/autowol/service/wake", {'host': hId || hName}, function(wdata, wstatus) {
                            BootstrapDialog.show({
                                title: "{{ lang._('Wake-on-LAN') }}",
                                message: wdata.response || "Pacote WoL enviado para " + hName,
                                buttons: [{ label: "OK", action: function(d) { d.close(); loadStatus(); loadLogs(); } }]
                            });
                        });
                    });
                } else {
                    $("#status_container").html(
                        "<div class='alert alert-info'><i class='fa fa-info-circle'></i> {{ lang._('Nenhum dado de status retornado. Clique em Checar Hosts Agora no topo.') }}</div>"
                    );
                }
            });
        }

        // Carrega logs de execução do backend
        function loadLogs() {
            ajaxCall("/api/autowol/service/logs", {}, function(data, status) {
                var content = data.logs || "{{ lang._('Nenhum log registrado ainda.') }}";
                var term = $("#log_terminal");
                term.text(content);
                term.scrollTop(term[0].scrollHeight);
            });
        }

        // Limpar logs
        $("#btn_clear_logs").click(function() {
            BootstrapDialog.confirm({
                title: "{{ lang._('Limpar Logs') }}",
                message: "{{ lang._('Deseja realmente apagar o histórico de logs do AutoWoL?') }}",
                type: BootstrapDialog.TYPE_WARNING,
                btnOKLabel: "{{ lang._('Limpar') }}",
                btnCancelLabel: "{{ lang._('Cancelar') }}",
                callback: function(result) {
                    if (result) {
                        ajaxCall("/api/autowol/service/clearLogs", {}, function(data, status) {
                            loadLogs();
                        });
                    }
                }
            });
        });

        $("#btn_refresh_logs").click(function() {
            loadLogs();
        });

        // Alternador de atualização automática de logs
        $("#chk_live_logs").change(function() {
            if ($(this).is(":checked")) {
                loadLogs();
                logTimer = setInterval(loadLogs, 3000);
            } else {
                if (logTimer) {
                    clearInterval(logTimer);
                    logTimer = null;
                }
            }
        });

        $('a[data-toggle="tab"]').on('shown.bs.tab', function (e) {
            var target = $(e.target).attr('href');
            if (target === '#tab_status') {
                loadStatus();
            } else if (target === '#tab_logs') {
                loadLogs();
            }
        });

        // Carregamento inicial do status
        loadStatus();
    });
</script>

<div class="content-box" style="padding-bottom: 1.5em;">
    <div class="col-xs-12">
        <div class="pull-right" style="margin-top: 15px; margin-bottom: 15px;">
            <button class="btn btn-default" id="btn_check_now" type="button">
                <i class="fa fa-refresh" id="btn_check_icon"></i> {{ lang._('Checar Hosts Agora') }}
            </button>
            <button class="btn btn-primary" id="btn_apply" type="button">
                <i class="fa fa-check" id="btn_apply_icon"></i> {{ lang._('Salvar e Aplicar Alterações') }}
            </button>
        </div>
    </div>
</div>

<div class="content-box">
    <ul class="nav nav-tabs" data-tabs="tabs" id="maintabs">
        <li class="active"><a data-toggle="tab" href="#tab_hosts"><i class="fa fa-server"></i> {{ lang._('Máquinas / Servidores') }}</a></li>
        <li><a data-toggle="tab" href="#tab_general"><i class="fa fa-sliders"></i> {{ lang._('Configurações Gerais') }}</a></li>
        <li><a data-toggle="tab" href="#tab_notifications"><i class="fa fa-bell"></i> {{ lang._('Canais de Notificação') }}</a></li>
        <li><a data-toggle="tab" href="#tab_status" id="tab_status_btn"><i class="fa fa-heartbeat"></i> {{ lang._('Status em Tempo Real') }}</a></li>
        <li><a data-toggle="tab" href="#tab_logs" id="tab_logs_btn"><i class="fa fa-terminal"></i> {{ lang._('Logs de Execução') }}</a></li>
    </ul>

    <div class="tab-content content-box tab-content">
        <!-- ABA 1: HOSTS -->
        <div id="tab_hosts" class="tab-pane fade in active">
            <div class="content-box" style="padding: 10px;">
                <table id="grid-hosts" class="table table-condensed table-hover table-striped" data-editDialog="dialogHost">
                    <thead>
                        <tr>
                            <th data-column-id="enabled" data-width="6em" data-type="string" data-formatter="rowtoggle">{{ lang._('Ativo') }}</th>
                            <th data-column-id="name" data-type="string">{{ lang._('Nome') }}</th>
                            <th data-column-id="ip" data-type="string">{{ lang._('IP') }}</th>
                            <th data-column-id="mac" data-type="string">{{ lang._('MAC') }}</th>
                            <th data-column-id="check_method" data-type="string">{{ lang._('Método') }}</th>
                            <th data-column-id="max_retries" data-type="string">{{ lang._('Tentativas') }}</th>
                            <th data-column-id="commands" data-formatter="commands" data-sortable="false">{{ lang._('Ações') }}</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                    <tfoot>
                        <tr>
                            <td></td>
                            <td colspan="5"></td>
                            <td>
                                <button data-action="add" type="button" class="btn btn-xs btn-default"><span class="fa fa-plus"></span> {{ lang._('Adicionar Máquina') }}</button>
                            </td>
                        </tr>
                    </tfoot>
                </table>
            </div>
        </div>

        <!-- ABA 2: CONFIGURAÇÕES GERAIS -->
        <div id="tab_general" class="tab-pane fade">
            <div class="content-box" style="padding: 15px;">
                {{ partial("layout_partials/base_form", ['fields': generalForm, 'id': 'frm_general_settings']) }}
                <div class="col-md-12">
                    <hr />
                    <button class="btn btn-primary" id="btn_save_general" type="button"><i class="fa fa-save"></i> {{ lang._('Salvar Configurações Gerais') }}</button>
                </div>
            </div>
        </div>

        <!-- ABA 3: NOTIFICAÇÕES -->
        <div id="tab_notifications" class="tab-pane fade">
            <div class="content-box" style="padding: 15px;">
                <div class="alert alert-info">
                    <i class="fa fa-info-circle"></i> {{ lang._('Ative um ou mais canais de alerta. Você pode testar individualmente cada canal usando os botões abaixo.') }}
                </div>
                {{ partial("layout_partials/base_form", ['fields': notificationsForm, 'id': 'frm_notifications']) }}
                <div class="col-md-12">
                    <hr />
                    <button class="btn btn-primary" id="btn_save_notifications" type="button"><i class="fa fa-save"></i> {{ lang._('Salvar Notificações') }}</button>
                    <div class="btn-group pull-right">
                        <button type="button" class="btn btn-default dropdown-toggle" data-toggle="dropdown" aria-haspopup="true" aria-expanded="false">
                            <i class="fa fa-paper-plane"></i> {{ lang._('Testar Disparo de Alerta') }} <span class="caret"></span>
                        </button>
                        <ul class="dropdown-menu">
                            <li><a href="javascript:void(0);" class="btn-test-alert" data-channel="whatsapp"><i class="fa fa-whatsapp text-success"></i> Testar WhatsApp</a></li>
                            <li><a href="javascript:void(0);" class="btn-test-alert" data-channel="telegram"><i class="fa fa-paper-plane text-info"></i> Testar Telegram</a></li>
                            <li><a href="javascript:void(0);" class="btn-test-alert" data-channel="email"><i class="fa fa-envelope text-warning"></i> Testar Email</a></li>
                            <li><a href="javascript:void(0);" class="btn-test-alert" data-channel="sms"><i class="fa fa-comment text-primary"></i> Testar SMS</a></li>
                            <li><a href="javascript:void(0);" class="btn-test-alert" data-channel="webhook"><i class="fa fa-globe"></i> Testar Webhook / Discord</a></li>
                            <li role="separator" class="divider"></li>
                            <li><a href="javascript:void(0);" class="btn-test-alert" data-channel="all"><i class="fa fa-bullhorn text-danger"></i> <strong>Testar Todos os Ativos</strong></a></li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>

        <!-- ABA 4: STATUS EM TEMPO REAL -->
        <div id="tab_status" class="tab-pane fade">
            <div class="content-box" style="padding: 15px;">
                <div class="pull-right" style="margin-bottom: 10px;">
                    <button class="btn btn-sm btn-default" onclick="loadStatus();" type="button">
                        <i class="fa fa-refresh"></i> {{ lang._('Atualizar Status') }}
                    </button>
                </div>
                <h4><i class="fa fa-heartbeat"></i> {{ lang._('Estado Atual das Máquinas Cadastradas') }}</h4>
                <div id="status_container" style="margin-top: 15px;">
                    <p class="text-muted"><i class="fa fa-spinner fa-spin"></i> {{ lang._('Carregando status dos hosts...') }}</p>
                </div>
            </div>
        </div>

        <!-- ABA 5: LOGS DE EXECUÇÃO -->
        <div id="tab_logs" class="tab-pane fade">
            <div class="content-box" style="padding: 15px;">
                <div class="row" style="margin-bottom: 10px;">
                    <div class="col-md-6">
                        <h4><i class="fa fa-terminal"></i> {{ lang._('Logs do Sistema (/var/log/autowol.log)') }}</h4>
                    </div>
                    <div class="col-md-6 text-right">
                        <label style="margin-right: 15px; font-weight: normal; cursor: pointer;">
                            <input type="checkbox" id="chk_live_logs"> {{ lang._('Atualização em Tempo Real (3s)') }}
                        </label>
                        <button class="btn btn-sm btn-default" id="btn_refresh_logs" type="button">
                            <i class="fa fa-refresh"></i> {{ lang._('Atualizar') }}
                        </button>
                        <button class="btn btn-sm btn-danger" id="btn_clear_logs" type="button">
                            <i class="fa fa-trash"></i> {{ lang._('Limpar Logs') }}
                        </button>
                    </div>
                </div>
                <pre id="log_terminal" style="background-color: #1a1a1a; color: #39ff14; font-family: 'Consolas', 'Courier New', monospace; font-size: 12px; padding: 15px; height: 480px; overflow-y: scroll; border-radius: 4px; white-space: pre-wrap; word-break: break-all; border: 1px solid #333;">{{ lang._('Carregando logs...') }}</pre>
            </div>
        </div>
    </div>
</div>

{# Modal Dialog para Adicionar/Editar Host #}
{{ partial("layout_partials/base_dialog", ['fields': dialogHost, 'id': 'dialogHost', 'label': lang._('Configurar Máquina para AutoWoL')]) }}
