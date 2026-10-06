{#
 # Copyright (C) 2026 AutoWoL Project
 # All rights reserved.
 #}

<script>
    $(document).ready(function() {
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
                BootstrapDialog.confirm({
                    title: "{{ lang._('Wake-on-LAN') }}",
                    message: "{{ lang._('Deseja enviar o pacote Wake-on-LAN para: ') }}<strong>" + hostName + "</strong>?",
                    type: BootstrapDialog.TYPE_INFO,
                    btnOKLabel: "{{ lang._('Enviar WoL') }}",
                    btnCancelLabel: "{{ lang._('Cancelar') }}",
                    callback: function(result) {
                        if (result) {
                            ajaxCall("/api/autowol/service/wake", {'host': hostName}, function(data, status) {
                                BootstrapDialog.show({
                                    title: "{{ lang._('Resultado WoL') }}",
                                    message: data.response || "{{ lang._('Pacote enviado com sucesso!') }}",
                                    buttons: [{
                                        label: "{{ lang._('Fechar') }}",
                                        action: function(dialog) { dialog.close(); }
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
                        action: function(dialog) { dialog.close(); }
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
                BootstrapDialog.show({
                    title: "{{ lang._('Checagem Executada') }}",
                    message: "<pre>" + JSON.stringify(data.data, null, 2) + "</pre>",
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

        // Carrega aba de status em tempo real
        function loadStatus() {
            ajaxCall("/api/autowol/service/status", {}, function(data, status) {
                if (data.data) {
                    var html = "<table class='table table-striped table-hover'><thead><tr><th>Host</th><th>Status</th><th>Tentativas</th><th>Última Vez Online</th></tr></thead><tbody>";
                    for (var h in data.data) {
                        var item = data.data[h];
                        var badge = item.status === "ONLINE" ? "label-success" : (item.status === "WAKING" ? "label-warning" : "label-danger");
                        html += "<tr>";
                        html += "<td><strong>" + h + "</strong></td>";
                        html += "<td><span class='label " + badge + "'>" + (item.status || "UNKNOWN") + "</span></td>";
                        html += "<td>" + (item.attempts || 0) + "</td>";
                        html += "<td>" + (item.last_seen_online || "Nunca") + "</td>";
                        html += "</tr>";
                    }
                    html += "</tbody></table>";
                    $("#status_container").html(html);
                }
            });
        }

        $('a[data-toggle="tab"]').on('shown.bs.tab', function (e) {
            if ($(e.target).attr('href') === '#tab_status') {
                loadStatus();
            }
        });
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
                <h4><i class="fa fa-heartbeat"></i> {{ lang._('Estado Atual das Máquinas') }}</h4>
                <div id="status_container">
                    <p class="text-muted"><i class="fa fa-spinner fa-spin"></i> {{ lang._('Carregando status dos hosts...') }}</p>
                </div>
            </div>
        </div>
    </div>
</div>

{# Modal Dialog para Adicionar/Editar Host #}
{{ partial("layout_partials/base_dialog", ['fields': dialogHost, 'id': 'dialogHost', 'label': lang._('Configurar Máquina para AutoWoL')]) }}
