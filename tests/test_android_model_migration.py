"""Compile the actual Android migration policy against synthetic config envelopes."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
JAVA_SOURCE = ROOT / 'android/standalone/app/src/main/java/cn/zhiheng/mobile/ModelConfigMigration.java'
JAVA_TEST = r'''
package cn.zhiheng.mobile;

public final class MigrationPolicyTest {
    private static final String OLD = "{\"ai\":{\"api_key\":\"synthetic-old-key\"}}";
    private static final String NEXT = "{\"ai\":{\"api_key\":\"synthetic-new-key\"}}";
    private static ModelConfigMigration.Config config(String raw, String endpoint, String model, String vision, String protocol) {
        return new ModelConfigMigration.Config(raw, endpoint, model, vision, protocol);
    }
    private static void expect(String name, String expected, String actual) {
        if (expected == null ? actual != null : !expected.equals(actual)) throw new AssertionError(name);
    }
    public static void main(String[] args) {
        ModelConfigMigration.Config next = config(NEXT,"https://code.leessmin.com/v1","gpt-5.5","gpt-5.5","chat_completions");
        ModelConfigMigration.Config old = config(OLD,"https://cc-vibe.com/v1","gpt-5.5","gpt-5.5","chat_completions");
        expect("whole config and new credential",NEXT,ModelConfigMigration.selectForLeessminRelease(old,next,false));
        expect("migration executes once",OLD,ModelConfigMigration.selectForLeessminRelease(old,next,true));
        expect("no embedded bundle",OLD,ModelConfigMigration.selectForLeessminRelease(old,null,false));
        expect("no saved config handled by installation fallback",null,ModelConfigMigration.selectForLeessminRelease(null,next,false));
        for (String endpoint : new String[]{"https://cc-vibe.com/v1/"," https://server.max-tabs.com/v1/// "}) {
            expect("legacy endpoint normalization",NEXT,ModelConfigMigration.selectForLeessminRelease(config(OLD,endpoint,"gpt-5.5","","auto"),next,false));
        }
        for (String endpoint : new String[]{"https://www.vibecd.cc/v1","http://47.110.38.211:8080/v1"}) {
            expect("older opus installation",NEXT,ModelConfigMigration.selectForLeessminRelease(config(OLD,endpoint,"claude-opus-4-8",null,""),next,false));
        }
        for (String endpoint : new String[]{"https://example.com/v1","https://code.leessmin.com/v1","https://cc-vibe.com/v2","https://cc-vibe.com.evil.example/v1"}) {
            expect("manual service preserved",OLD,ModelConfigMigration.selectForLeessminRelease(config(OLD,endpoint,"gpt-5.5","gpt-5.5","chat_completions"),next,false));
        }
        expect("manual text model preserved",OLD,ModelConfigMigration.selectForLeessminRelease(config(OLD,"https://cc-vibe.com/v1","custom-model","custom-model","chat_completions"),next,false));
        expect("manual vision model preserved",OLD,ModelConfigMigration.selectForLeessminRelease(config(OLD,"https://cc-vibe.com/v1","gpt-5.5","custom-vision","chat_completions"),next,false));
        expect("manual protocol preserved",OLD,ModelConfigMigration.selectForLeessminRelease(config(OLD,"https://cc-vibe.com/v1","gpt-5.5","gpt-5.5","responses"),next,false));
        expect("wrong package endpoint",OLD,ModelConfigMigration.selectForLeessminRelease(old,config(NEXT,"https://example.com/v1","gpt-5.5","gpt-5.5","chat_completions"),false));
        expect("wrong package model",OLD,ModelConfigMigration.selectForLeessminRelease(old,config(NEXT,"https://code.leessmin.com/v1","other","other","chat_completions"),false));
        expect("wrong package protocol",OLD,ModelConfigMigration.selectForLeessminRelease(old,config(NEXT,"https://code.leessmin.com/v1","gpt-5.5","gpt-5.5","responses"),false));
        ModelConfigMigration.Config sol = config(NEXT,"https://code.leessmin.com/v1","gpt-6.1-sol","gpt-6.1-sol","chat_completions");
        ModelConfigMigration.Config current = config(OLD,"https://code.leessmin.com/v1","gpt-5.5","gpt-5.5","chat_completions");
        expect("sol replaces previous bundled model",NEXT,ModelConfigMigration.selectForSolRelease(current,sol,false));
        expect("sol migrates legacy install",NEXT,ModelConfigMigration.selectForSolRelease(old,sol,false));
        expect("sol executes once",OLD,ModelConfigMigration.selectForSolRelease(current,sol,true));
        expect("sol absent bundle",OLD,ModelConfigMigration.selectForSolRelease(current,null,false));
        expect("sol new install fallback",null,ModelConfigMigration.selectForSolRelease(null,sol,false));
        for (ModelConfigMigration.Config custom : new ModelConfigMigration.Config[]{
            config(OLD,"https://example.com/v1","gpt-5.5","gpt-5.5","chat_completions"),
            config(OLD,"https://code.leessmin.com/v1","custom","custom","chat_completions"),
            config(OLD,"https://code.leessmin.com/v1","gpt-5.5","custom-vision","chat_completions"),
            config(OLD,"https://code.leessmin.com/v1","gpt-5.5","gpt-5.5","responses"),
            config(OLD,"https://code.leessmin.com/v1","gpt-6.1-sol","gpt-6.1-sol","chat_completions")}) {
            expect("sol preserves manual settings",OLD,ModelConfigMigration.selectForSolRelease(custom,sol,false));
        }
        expect("sol validates bundled target",OLD,ModelConfigMigration.selectForSolRelease(current,next,false));
        System.out.println("PASS: complete configuration migration and manual service preservation");
    }
}
'''


class AndroidModelMigrationTests(unittest.TestCase):
    def test_upgrade_migrates_known_defaults_and_preserves_custom_services(self):
        candidates = []
        if os.environ.get('JAVA_HOME'):
            candidates.append(Path(os.environ['JAVA_HOME']) / 'bin')
        if shutil.which('javac'):
            candidates.append(Path(shutil.which('javac')).parent)
        candidates.append(ROOT.parent / 'moviedl/.tool-downloads/jdk17/jdk-17.0.20.1+1/bin')
        java_bin = next((folder for folder in candidates if (folder / 'javac.exe').is_file()
                         or (folder / 'javac').is_file()), None)
        if java_bin is None:
            self.skipTest('Java compiler is unavailable for Android migration policy verification')
        suffix = '.exe' if (java_bin / 'javac.exe').is_file() else ''
        with tempfile.TemporaryDirectory(prefix='zhiheng-android-migration-') as folder:
            test_source = Path(folder) / 'MigrationPolicyTest.java'
            test_source.write_text(JAVA_TEST, encoding='utf-8')
            compiled = subprocess.run([str(java_bin / ('javac' + suffix)), '-encoding', 'UTF-8',
                '-d', folder, str(JAVA_SOURCE), str(test_source)], capture_output=True, text=True, timeout=30)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            checked = subprocess.run([str(java_bin / ('java' + suffix)), '-cp', folder,
                'cn.zhiheng.mobile.MigrationPolicyTest'], capture_output=True, text=True, timeout=15)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertIn('PASS:', checked.stdout)


if __name__ == '__main__':
    unittest.main()
