"""Offline APK build with an existing Android SDK/JDK; no Gradle downloads."""
import argparse,os,subprocess,zipfile,hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--sdk',default=r'F:\aiworkspace\codexworkspace\moviedl\.local-android-sdk')
parser.add_argument('--jdk',default=r'F:\aiworkspace\codexworkspace\moviedl\.tool-downloads\jdk17\jdk-17.0.20.1+1')
args=parser.parse_args();sdk=Path(args.sdk);jdk=Path(args.jdk)
build=ROOT/'build';build.mkdir(exist_ok=True);classes=build/'classes';classes.mkdir(exist_ok=True)
tools=sdk/'build-tools'/'36.0.0';platform=sdk/'platforms'/'android-36'/'android.jar'
release=ROOT.parent/'release'/'android-20260917';release.mkdir(parents=True,exist_ok=True)
def run(*cmd):subprocess.run([str(x) for x in cmd],check=True)
run(tools/'aapt.exe','package','-f','-M',ROOT/'AndroidManifest.xml','-S',ROOT/'res','-I',platform,'-F',build/'resources.apk')
run(jdk/'bin/javac.exe','-encoding','UTF-8','-source','8','-target','8','-bootclasspath',str(platform)+os.pathsep+str(tools/'core-lambda-stubs.jar'),'-d',classes,*ROOT.glob('src/**/*.java'))
run(jdk/'bin/java.exe','-cp',tools/'lib/d8.jar','com.android.tools.r8.D8','--lib',platform,'--min-api','26','--output',build,*classes.glob('**/*.class'))
with zipfile.ZipFile(build/'resources.apk') as source,zipfile.ZipFile(build/'unsigned.apk','w',zipfile.ZIP_DEFLATED) as target:
    for item in source.infolist():target.writestr(item,source.read(item.filename))
    target.write(build/'classes.dex','classes.dex')
run(tools/'zipalign.exe','-f','4',build/'unsigned.apk',build/'aligned.apk')
private=ROOT.parent/'.mobile-private';private.mkdir(exist_ok=True);key=private/'android-test.jks'
if not key.exists():run(jdk/'bin/keytool.exe','-genkeypair','-keystore',key,'-storepass','android','-keypass','android','-alias','zhiheng-test','-dname','CN=Zhiheng Local Test','-keyalg','RSA','-keysize','2048','-validity','10000')
apk=release/'Zhiheng-0.1.0-test.apk'
run(jdk/'bin/java.exe','-jar',tools/'lib/apksigner.jar','sign','--ks',key,'--ks-key-alias','zhiheng-test','--ks-pass','pass:android','--key-pass','pass:android','--out',apk,build/'aligned.apk')
run(jdk/'bin/java.exe','-jar',tools/'lib/apksigner.jar','verify','--verbose',apk)
run(tools/'aapt.exe','dump','badging',apk)
(release/'SHA256.txt').write_text(hashlib.sha256(apk.read_bytes()).hexdigest()+'  '+apk.name+'\n',encoding='utf-8')
print('APK:',apk)
