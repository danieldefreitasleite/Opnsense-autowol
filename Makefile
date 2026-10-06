# AutoWoL Makefile for FreeBSD / OPNsense Port & Package

PORTNAME=	os-autowol
PORTVERSION=	1.0.0
PORTREVISION=	1
CATEGORIES=	sysutils net
COMMENT=	OPNsense Web GUI Plugin: AutoWoL and Host Monitor with Multi-Channel Alerts

LICENSE=	BSD2CLAUSE

USES=		python:3.8+

NO_BUILD=	yes
NO_ARCH=	yes

do-install:
	${MKDIR} ${STAGEDIR}${PREFIX}/etc/autowol
	${MKDIR} ${STAGEDIR}${PREFIX}/etc/rc.d
	${MKDIR} ${STAGEDIR}${PREFIX}/opnsense/scripts/autowol/notifiers
	${MKDIR} ${STAGEDIR}${PREFIX}/opnsense/service/conf/actions.d
	${MKDIR} ${STAGEDIR}${PREFIX}/opnsense/service/templates/OPNsense/AutoWoL
	${MKDIR} ${STAGEDIR}${PREFIX}/opnsense/mvc/app/models/OPNsense/AutoWoL/Menu
	${MKDIR} ${STAGEDIR}${PREFIX}/opnsense/mvc/app/models/OPNsense/AutoWoL/ACL
	${MKDIR} ${STAGEDIR}${PREFIX}/opnsense/mvc/app/controllers/OPNsense/AutoWoL/Api
	${MKDIR} ${STAGEDIR}${PREFIX}/opnsense/mvc/app/controllers/OPNsense/AutoWoL/forms
	${MKDIR} ${STAGEDIR}${PREFIX}/opnsense/mvc/app/views/OPNsense/AutoWoL

	# Config & rc.d
	${INSTALL_DATA} ${WRKSRC}/etc/autowol/config.sample.json ${STAGEDIR}${PREFIX}/etc/autowol/config.sample.json
	${INSTALL_SCRIPT} ${WRKSRC}/etc/rc.d/autowol ${STAGEDIR}${PREFIX}/etc/rc.d/autowol

	# Backend Python scripts
	${INSTALL_SCRIPT} ${WRKSRC}/opnsense/scripts/autowol/*.py ${STAGEDIR}${PREFIX}/opnsense/scripts/autowol/
	${INSTALL_SCRIPT} ${WRKSRC}/opnsense/scripts/autowol/notifiers/*.py ${STAGEDIR}${PREFIX}/opnsense/scripts/autowol/notifiers/

	# Configd & Templates
	${INSTALL_DATA} ${WRKSRC}/opnsense/service/conf/actions.d/actions_autowol.conf ${STAGEDIR}${PREFIX}/opnsense/service/conf/actions.d/actions_autowol.conf
	${CP} -R ${WRKSRC}/opnsense/service/templates/OPNsense/AutoWoL/* ${STAGEDIR}${PREFIX}/opnsense/service/templates/OPNsense/AutoWoL/

	# MVC App (Model, View, Controller, Forms, ACL, Menu)
	${CP} -R ${WRKSRC}/opnsense/mvc/app/models/OPNsense/AutoWoL/* ${STAGEDIR}${PREFIX}/opnsense/mvc/app/models/OPNsense/AutoWoL/
	${CP} -R ${WRKSRC}/opnsense/mvc/app/controllers/OPNsense/AutoWoL/* ${STAGEDIR}${PREFIX}/opnsense/mvc/app/controllers/OPNsense/AutoWoL/
	${CP} -R ${WRKSRC}/opnsense/mvc/app/views/OPNsense/AutoWoL/* ${STAGEDIR}${PREFIX}/opnsense/mvc/app/views/OPNsense/AutoWoL/

.include <bsd.port.mk>
