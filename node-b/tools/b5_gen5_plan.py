"""gen4→5 Wi-Fi最小字节计划及两级回退，纯离线，不加载SDK。"""
import json
import struct
import b5_sector3_plan as p
require=p.require;sha=p.sha


def non_wifi(record):
    result=bytearray(record);result[12:20]=bytes(8);result[32:130]=bytes(98)
    return bytes(result)


def wifi_record(old,wifi):
    generation,minimum,fields=p.parse_record(old)
    require(generation==4 and fields['username']==b'b5-gateway' and fields['client_id']==b'b5-c-isolated','G5_SOURCE_IDENTITY')
    values={'ssid':p.field_bytes(wifi['ssid'],33),'wifi_password':p.field_bytes(wifi['password'],65,False)}
    require(any(fields[k]!=v for k,v in values.items()),'G5_WIFI_UNCHANGED')
    result=bytearray(old)
    for key,offset,width in p.FIELDS:
        if key in values:result[24+offset:24+offset+width]=values[key]+bytes(width-len(values[key]))
    struct.pack_into('<I',result,12,5);struct.pack_into('<I',result,16,p.record_crc(result))
    require(non_wifi(result)==non_wifi(old),'G5_NON_WIFI_CHANGE')
    require(p.parse_record(result)[:2]==(5,minimum),'G5_RECORD_BUILD')
    return bytes(result)


def stage(sector):return sector[:20]+b'\xff'*4+sector[24:]


def build(current,original,wifi,options,identity):
    require(len(current)==len(original)==1048576 and len(options)==16,'G5_SOURCE_SIZES')
    require(sha(current[:p.APP_BYTES])==p.APP_SHA and sha(original)==p.CURRENT_FULL_SHA,'G5_SOURCE_IMAGES')
    require(current[p.APP_BYTES:p.START]==original[p.APP_BYTES:p.START] and current[p.END:]==original[p.END:],'G5_PROTECTED_OR_APP_TAIL')
    require(current[p.START+336:p.END]==original[p.START+336:p.END],'G5_SECTOR_TAIL')
    require(p.parse_record(original[p.START:p.START+336])[0]==3,'G5_ORIGINAL_GEN3')
    ident=json.loads(identity);require(ident['capacity_kib']==1024,'G5_IDENTITY_CAPACITY')
    record=wifi_record(current[p.START:p.START+336],wifi)
    sector=record+current[p.START+336:p.END]
    final=current[:p.START]+sector+current[p.END:]
    precommit=current[:p.START]+stage(sector)+current[p.END:]
    gen3=current[:p.START]+original[p.START:p.END]+current[p.END:]
    require(original[:p.START]+gen3[p.START:]==original,'G5_RCFG_THEN_RAPP')
    files={'gen4-full-private.bin':current,'gen5-full-private.bin':final,'gen5-precommit-full-private.bin':precommit,
        'gen5-record-private.bin':record,'gen5-record-uncommitted-private.bin':record[:20]+b'\xff'*4+record[24:],
        'gen5-sector-private.bin':sector,'gen5-stage-sector-private.bin':stage(sector),
        'gen4-stage-sector-private.bin':stage(current[p.START:p.END]),'gen3-stage-sector-private.bin':stage(original[p.START:p.END]),
        'B5-gen3-full-private.bin':gen3,'original-C24104-full-private.bin':original,
        'options-private.bin':options,'identity-private.json':identity}
    manifest={'schema':'B5_GEN5_WIFI_ONLY_PACKAGE_V1','hardware_execution_enabled':False,
        'fresh_target_binding':'HISTORICAL_GEN4_TEMPLATE_REQUIRES_DOUBLE_FULL_OPTIONS_AND_IDENTITY_MATCH_BEFORE_UNLOCK',
        'generation_from':4,'generation_to':5,'sector_range':[0x0800c000,0x08010000],
        'record_bytes':336,'sector_tail_preserved_bytes':16048,'only_fields_changed':['ssid','wifi_password','generation','CRC'],
        'MQTT_identity_TLS_minimum_epoch_unchanged':True,'APP42552_unchanged':True,'options_sector7_sector11_unchanged':True,
        'full_original_restore_target':'PRE_B5_C24104_CHECKPOINT_NOT_HISTORICAL_H3',
        'rollback_objects':['5_TO_4_B5_CONFIGURATION','5_TO_3_CONFIG_THEN_SEPARATE_APP_TO_C24104'],
        'files':{name:{'bytes':len(blob),'sha256':sha(blob)} for name,blob in files.items()}}
    return manifest,files
