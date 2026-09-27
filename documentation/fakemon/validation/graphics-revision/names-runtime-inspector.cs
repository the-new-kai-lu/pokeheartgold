using System.Security.Cryptography;
using System.Text.Json;
using PKHeX.Core;
if(args.Length<3)throw new ArgumentException("fixture <input.sav> <output.sav> OR check <before.sav> <after.sav> <report.json>");
SAV4HGSS Read(string path) {
    var s=SaveUtil.GetSaveFile(File.ReadAllBytes(path)) as SAV4HGSS ?? throw new Exception("Not HGSS");
    if(!s.IsFakemonStock || !s.ChecksumsValid)throw new Exception("Profile or save checksum failure");
    return s;
}
string Hash(string path)=>Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();
var before=Read(args[1]);
if(args[0]=="fixture") {
    var a=(PK4)before.GetPartySlotAtIndex(1);a.Nickname="Cinder";a.IsNicknamed=true;before.SetPartySlotAtIndex(a,1);
    var b=(PK4)before.GetPartySlotAtIndex(2);b.Nickname="Sedgling";b.IsNicknamed=true;before.SetPartySlotAtIndex(b,2);
    File.WriteAllBytes(args[2],before.Write().ToArray());
    var oldSave=Read(args[1]);var made=Read(args[2]);var changes=new List<object>();
    for(int i=0;i<3;i++) {
        var old=oldSave.GetPartySlotAtIndex(i);var next=made.GetPartySlotAtIndex(i);
        var left=old.Data.ToArray();var right=next.Data.ToArray();
        var offsets=Enumerable.Range(0,left.Length).Where(j=>left[j]!=right[j]).ToArray();
        if(!offsets.All(j=>j==6 || j==7 || j==0x3B || j>=0x48 && j<0x5E))throw new Exception("Fixture edited unrelated Pokemon fields");
        if(i==0 && !left.SequenceEqual(right))throw new Exception("Fixture changed default Voltuff");
        if(!next.ChecksumValid)throw new Exception("Fixture Pokemon checksum invalid");
        changes.Add(new{slot=i,species=next.Species,pid=next.PID,original_nickname=old.Nickname,new_nickname=next.Nickname,nickname_flag=next.IsNicknamed,changed_decrypted_offsets=offsets.Select(j=>"0x"+j.ToString("X2")).ToArray()});
    }
    File.WriteAllText(Path.ChangeExtension(args[2],"json"),JsonSerializer.Serialize(new{provenance="Original genuine post-Elm save; only two nicknames and nickname flags edited",original_save=args[1],original_sha256=Hash(args[1]),fixture=args[2],fixture_sha256=Hash(args[2]),changes},new JsonSerializerOptions{WriteIndented=true})+"\n");
    Console.WriteLine("Created nickname-only fixture: Voltuff default, Cinder nicknamed, Sedgling explicitly nicknamed.");
    return;
}
var after=Read(args[2]);
int checks=0;
void Check(bool ok,string message){if(!ok)throw new Exception(message);checks++;}
Check(before.PartyCount==3 && after.PartyCount==3,"Party count changed");
Check(before.ID32==after.ID32 && before.OT==after.OT,"Player identity changed");
var rows=new List<object>();
for(int i=0;i<3;i++) {
    var a=(PK4)before.GetPartySlotAtIndex(i);var b=(PK4)after.GetPartySlotAtIndex(i);
    Check(a.ChecksumValid && b.ChecksumValid,"Pokemon checksum invalid");
    Check(a.IsFakemonStock && b.IsFakemonStock,"Profile changed");
    var expected=a.IsNicknamed?a.Nickname:a.Nickname.ToUpperInvariant();
    Check(b.Nickname==expected,$"Wrong nickname {i}: {b.Nickname}, expected {expected}");
    Check(a.IsNicknamed==b.IsNicknamed,"Nickname flag changed");
    Check(a.PID==b.PID && a.ID32==b.ID32,"Pokemon identity changed");
    var left=a.Data.ToArray();var right=b.Data.ToArray();
    var changed=Enumerable.Range(0,left.Length).Where(j=>left[j]!=right[j]).ToArray();
    Check(changed.All(j=>j==6 || j==7 || j>=0x48 && j<0x5E),"Unrelated Pokemon bytes changed: "+string.Join(',',changed.Select(j=>j.ToString("X"))));
    if(a.IsNicknamed)Check(left.SequenceEqual(right),"Genuine nickname Pokemon bytes changed");
    Check(a.CurrentLevel==b.CurrentLevel && a.EXP==b.EXP && a.Ability==b.Ability,"Growth/ability changed");
    Check(a.Stat_HPCurrent==b.Stat_HPCurrent && a.Stat_HPMax==b.Stat_HPMax && a.Stat_ATK==b.Stat_ATK && a.Stat_DEF==b.Stat_DEF && a.Stat_SPA==b.Stat_SPA && a.Stat_SPD==b.Stat_SPD && a.Stat_SPE==b.Stat_SPE,"Party stats changed");
    var startMoves=new ushort[]{a.Move1,a.Move2,a.Move3,a.Move4};var endMoves=new ushort[]{b.Move1,b.Move2,b.Move3,b.Move4};
    Check(startMoves.SequenceEqual(endMoves),"Moves changed");
    rows.Add(new {slot=i,species=a.Species,pid=a.PID,old_name=a.Nickname,new_name=b.Nickname,is_nicknamed=b.IsNicknamed,level=b.CurrentLevel,experience=b.EXP,ability=b.Ability,stats=new{hp=b.Stat_HPCurrent,max_hp=b.Stat_HPMax,atk=b.Stat_ATK,def=b.Stat_DEF,spa=b.Stat_SPA,spd=b.Stat_SPD,spe=b.Stat_SPE},moves=endMoves,checksum_valid=b.ChecksumValid,changed_decrypted_offsets=changed.Select(j=>"0x"+j.ToString("X2")).ToArray()});
}
var roundtrip=Read(args[2]);var exported=roundtrip.Write().ToArray();
var again=SaveUtil.GetSaveFile(exported) as SAV4HGSS ?? throw new Exception("Roundtrip failed");
Check(again.IsFakemonStock && again.ChecksumsValid,"Editor roundtrip checksum/profile failed");
for(int i=0;i<3;i++)Check(again.GetPartySlotAtIndex(i).Data.SequenceEqual(after.GetPartySlotAtIndex(i).Data),"Editor roundtrip changed Pokemon bytes");
var report=new{result="passed",checks,before_save=args[1],before_sha256=Hash(args[1]),after_save=args[2],after_sha256=Hash(args[2]),save_checksums_valid=true,party_records=rows,editor_roundtrip="valid_checksums_and_exact_Pokemon_bytes_preserved"};
Directory.CreateDirectory(Path.GetDirectoryName(args[3])!);
File.WriteAllText(args[3],JsonSerializer.Serialize(report,new JsonSerializerOptions{WriteIndented=true})+"\n");
Console.WriteLine($"PASS {checks} checks; all three Pokémon retain PID, EXP, stats, ability and moves, with only expected default-name case and checksum bytes changed.");
