"""统一候选定向Host回归；复用现有GCC、真实coreMQTT、模型/队列与ESP替身，无设备连接。"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--payload-stress',action='store_true');args=parser.parse_args()
    out=ROOT/'node-b/build'/('unified-host-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    out.mkdir()
    inc=['gateway/microphone','gateway/voice','gateway/mqtt/src','gateway/b5',
         'gateway/dual_can','gateway/canopen/src','gateway/third_party/CANopenNode',
         'gateway/third_party/coreMQTT/source/include','gateway/third_party/coreMQTT/source/interface']
    flags=['gcc','-std=c11','-D__USE_MINGW_ANSI_STDIO=1','-O1','-Wall','-Wextra','-Werror',*['-I'+str(ROOT/p) for p in inc]]
    shared=['gateway/microphone/mic_format.c','gateway/microphone/mic_protocol.c']
    transport=['gateway/mqtt/tests/mocks/mock_esp.c','gateway/mqtt/src/mqtt_transport_adapter.c',
        'gateway/data_model/model.c','gateway/storage/router.c','gateway/b5/b5_policy.c',
        *[f'gateway/third_party/coreMQTT/source/{n}.c' for n in ('core_mqtt','core_mqtt_serializer','core_mqtt_state')]]
    macros=['-DGATEWAY_MQTT_HOST_TEST','-DMP_B5_CLOUD_CANDIDATE','-DMP_B5_EGRESS_FINAL','-DMP_FRAME_MAX_SAMPLES=100',
        '-DMP_LIVE_CAPACITY=24','-DMP_CACHE_CAPACITY=56','-DMOCK_USERNAME="b5-gateway"','-DMOCK_CLIENT_ID="b5-c-isolated"']
    cases={'unified_transport':([*macros,'-DMP_FINAL_UNIFIED'],['gateway/microphone/test_unified_transport.c',*transport,*shared]),
        'unified_audio':(['-DMP_B5_EGRESS_FINAL','-DMP_CLOUD_VOICE'],['gateway/microphone/test_unified_audio.c',
            'gateway/microphone/unified_audio.c','gateway/voice/tts_queue.c','gateway/voice/tts_frame.c',*shared]),
        'unified_control':(['-flto','-fwhole-program','-DMP_FINAL_UNIFIED','-DMP_ABC_TRI_CANDIDATE','-DMP_B5_EGRESS_FINAL',
            '-DMP_FRAME_MAX_SAMPLES=100','-DMP_LIVE_CAPACITY=24','-DMP_CACHE_CAPACITY=56','-DCO_MULTIPLE_OD'],
            ['gateway/microphone/test_unified_control.c',*shared]),
        'scheduler_fixed':([*macros,'-DMP_FINAL_UNIFIED'],['gateway/microphone/test_unified_scheduler.c','gateway/storage/router.c','gateway/data_model/model.c','gateway/b5/b5_policy.c']),
        'scheduler_before':(macros,['gateway/microphone/test_unified_scheduler.c','gateway/storage/router.c','gateway/data_model/model.c','gateway/b5/b5_policy.c']),
        'can_software_replay':(['-Wno-unused-parameter',*macros,'-DMP_FINAL_UNIFIED','-DMP_ABC_TRI_CANDIDATE','-DB4_BXCAN_MMIO_TEST','-DABC_MMIO_INPUT','-DCO_MULTIPLE_OD'],
            ['gateway/microphone/test_unified_replay.c','gateway/dual_can/b4_bxcan.c','gateway/dual_can/b4_bus.c','gateway/dual_can/b4_gateway.c',
             'gateway/canopen/src/mp_od.c','gateway/data_model/model.c','gateway/storage/router.c',
             'gateway/third_party/CANopenNode/CANopen.c',*[str(p.relative_to(ROOT)) for p in sorted((ROOT/'gateway/third_party/CANopenNode/301').glob('*.c'))]]),
        'contention':([*macros,'-DMP_FINAL_UNIFIED','-DMP_ABC_TRI_CANDIDATE','-DMP_CLOUD_VOICE'],['gateway/microphone/test_unified_contention.c','gateway/mqtt/src/gateway_transport.c',*transport,*shared,'gateway/voice/tts_queue.c','gateway/voice/tts_frame.c']),
        'queued_clock':([*macros,'-flto','-fwhole-program','-DMP_FINAL_UNIFIED','-DCO_MULTIPLE_OD'],['gateway/microphone/test_unified_clock.c','gateway/canopen/src/mp_od.c','gateway/third_party/CANopenNode/301/CO_ODinterface.c']),
        'format':([],['gateway/microphone/test_format.c','gateway/microphone/mic_format.c']),
        'legacy_egress':(macros,['gateway/b5/test_egress_async.c','gateway/mqtt/src/gateway_transport.c',*transport])}
    for name in ('unified_transport','scheduler_fixed'):
        defines,files=cases[name]
        cases[name+'_no_audio']=([*defines,'-DMP_AUDIO_DISABLED'],files)
    field01_at=['-flto','-fwhole-program','-DGATEWAY_MQTT_HOST_TEST','-DMP_FIVE_FIELD01',
                '-DMP_B5_EGRESS_FINAL','-DMP_CAN_RX_IRQ']
    for case in ('wifi_failure','preflight'):
        cases['field01_'+case]=(field01_at,[f'gateway/mqtt/tests/test_field01_{case}.c',
            'gateway/mqtt/src/gateway_transport.c','gateway/mqtt/src/mqtt_transport_adapter.c'])
    cases['field01_control']=(['-flto','-fwhole-program','-Wno-unused-function','-Wno-return-type',
        '-DMP_FINAL_UNIFIED','-DMP_FIVE_APPLIANCE','-DMP_FIVE_NODE','-DMP_FIVE_FIELD01',
        '-DMP_B5_EGRESS_FINAL','-DMP_B5_CLOUD_CANDIDATE','-DMP_ABC_TRI_CANDIDATE',
        '-DMP_FRAME_MAX_SAMPLES=100','-DMP_LIVE_CAPACITY=24','-DMP_CACHE_CAPACITY=56','-DCO_MULTIPLE_OD'],
        ['gateway/microphone/test_field01_probe.c'])
    field_defines,field_files=cases['field01_control']
    cases['field01_profile_pair_control']=([*field_defines,'-DMP_AUDIO_DISABLED',
        '-DMP_TRANSPORT_PROFILE','-DMP_ESP_UART_230400','-DMP_ESP_PASSTHROUGH'],field_files)
    cases['field01_pass115_control']=([*field_defines,'-DMP_AUDIO_DISABLED',
        '-DMP_TRANSPORT_PROFILE','-DMP_ESP_PASSTHROUGH'],field_files)
    cases['field01_pass115_peer']=([*field01_at,*macros,'-Wno-unused-parameter','-DPLATFORM_HOST_TEST',
        '-DMP_FINAL_UNIFIED','-DMP_FIVE_NODE','-DMP_FIVE_APPLIANCE','-DMP_ABC_TRI_CANDIDATE',
        '-DMP_AUDIO_DISABLED','-DMP_TRANSPORT_PROFILE','-DMP_ESP_PASSTHROUGH'],
        ['gateway/b5/test_five_p3_egress.c',*transport[1:],*shared])
    peer_defines,peer_files=cases['field01_pass115_peer']
    cases['production_pass_lifecycle']=([flag for flag in peer_defines if flag!='-DMP_FIVE_FIELD01']+
        ['-DMP_PASS_LIFECYCLE','-DGATEWAY_TELEMETRY_SLOTS=4u'],peer_files)
    cases['production_esp_pf6_reset']=([],['gateway/mqtt/tests/test_esp_pf6_reset.c'])
    cases['field01_uart_retime']=(['-flto','-fwhole-program','-DMP_FIVE_FIELD01','-DMP_CAN_RX_IRQ',
        '-DMP_B5_EGRESS_FINAL','-DMP_B5_CLOUD_CANDIDATE'],['gateway/mqtt/tests/test_field01_uart_retime.c'])
    cases['field01_sntp_retry']=([*field01_at,'-DMP_H3_FRESH_SNTP','-DMP_B5_CLOUD_CANDIDATE'],
        ['gateway/b5/test_sntp_retry.c',*transport[1:]])
    cases['production_uart']=(['-flto','-fwhole-program','-DGATEWAY_MQTT_HOST_TEST','-DMP_ESP_UART_230400',
        '-DMP_TRANSPORT_PROFILE','-DMP_B5_EGRESS_FINAL','-DMP_CAN_RX_IRQ','-DMP_B5_CLOUD_CANDIDATE'],
        ['gateway/mqtt/tests/test_production_uart.c'])
    results=[]
    for name,(defines,files) in cases.items():
        exe=out/(name+'.exe');cmd=[*flags,*defines,*[str(ROOT/p) for p in files],'-o',str(exe)]
        p=subprocess.run(cmd,capture_output=True);(out/(name+'-compile.log')).write_bytes(p.stdout+p.stderr)
        r={'case':name,'compile_native_exit':p.returncode,'commands':[cmd],
           'source_SHA256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}}
        results.append(r)
        if not p.returncode:
            p=subprocess.run([str(exe)],capture_output=True,timeout=30)
            (out/(name+'-run.log')).write_bytes(p.stdout+p.stderr)
            r.update(run_native_exit=p.returncode,stdout=p.stdout.decode().strip())
            if name=='contention' and not p.returncode:
                q=subprocess.run([str(exe),'ABC'],capture_output=True,timeout=30)
                (out/'contention-ABC-run.log').write_bytes(q.stdout+q.stderr)
                r.update(ABC_run_native_exit=q.returncode,ABC_stdout=q.stdout.decode().strip())
                if q.returncode:p=q
                elif args.payload_stress:
                    q=subprocess.run([str(exe),'ABC','large-payload-300ms-ACK'],capture_output=True,timeout=30)
                    (out/'contention-payload-stress-run.log').write_bytes(q.stdout+q.stderr)
                    r.update(payload_stress_native_exit=q.returncode,payload_stress_stdout=q.stdout.decode().strip())
                    if q.returncode:p=q
        (out/'receipt.json').write_text(json.dumps({'scope':'HOST_ONLY_NOT_HARDWARE','results':results},indent=2)+'\n')
        print(json.dumps({k:v for k,v in r.items() if k not in ('commands','source_SHA256')}),flush=True)
        if p.returncode:print((p.stdout+p.stderr).decode(errors='replace')[-2500:]);return 1
    (ROOT/'node-b/build/unified-host-current-pointer.json').write_text(json.dumps({'out':str(out)})+'\n')
    return 0


if __name__=='__main__':raise SystemExit(main())
