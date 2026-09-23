# Samjon Memory Subject and Type Guidelines

**Document ID:** SAMJON-MEMORY-SUBJECT-TYPE-GUIDE-001  
**Version:** 1.0.0  
**Status:** Reference Guideline  
**Owner:** Samjon Memory Engineering  
**Approver:** Jeab  
**Last reviewed:** 2026-09-21  

---

## 1. Subject คืออะไร

`subject` คือ canonical identity ของสิ่งที่ Memory หรือ Collection กล่าวถึง ไม่ใช่ชื่อหัวข้อหรือประโยคอธิบาย

รูปแบบมาตรฐาน:

```text
<domain>:<canonical-id>
```

ตัวอย่าง:

```text
person:jeab
plant:monstera-bedroom
device:air-conditioner-bedroom
location:living-room
household:main-home
routine:bedtime
inventory:network-spares
```

กฎการตั้งชื่อ:

- ใช้ตัวพิมพ์เล็ก
- ใช้ภาษาอังกฤษสำหรับ identifier
- คั่นคำด้วย `-`
- มี domain นำหน้า
- หนึ่ง subject ต้องมีความหมายเดียวและคงที่
- ไม่ใส่สถานะ ค่า setting หรือรายละเอียดที่เปลี่ยนบ่อย
- ไม่ใส่ credential, token, security code หรือข้อมูลอ่อนไหว

ตัวอย่างที่ไม่ควรใช้เป็น subject:

```text
การรดน้ำ
แอร์ 25 องศา
มอนสเตอร่าที่ต้องรดน้ำพรุ่งนี้
ของในห้องเก็บของ
```

ข้อความเหล่านี้ควรเป็น `title` หรือ `raw_content`

---

## 2. Subject Domains ที่แนะนำ

Catalog เริ่มต้น:

```text
person
household
location
device
equipment
plant
pet
music
playlist
routine
activity
inventory
item
supply
service
system
integration
automation
topic
policy
project
test
```

ตัวอย่าง:

```text
person:jeab
household:main-home
location:storage-room
device:water-pump-main
equipment:network-rack
plant:monstera-bedroom
pet:cat-mali
music:morning-work
playlist:evening-relax
routine:bedtime
inventory:network-spares
item:spare-router
service:music-assistant
system:home-assistant
integration:frigate
automation:bedtime-lighting
topic:household-energy-saving
policy:guest-wifi
project:home-ai
test:lifecycle-purge
```

แนวทางสำคัญ:

- เลือก domain เดียวสำหรับแนวคิดเดียวกันอย่างสม่ำเสมอ
- หากชื่อหลายแบบหมายถึงสิ่งเดียวกัน ให้ใช้ Alias แทนการสร้างหลาย Subjects
- หากต้องอ้างอิงระบบภายนอก เช่น Home Assistant entity ให้เก็บ external reference ใน metadata แทนการใช้เป็น subject โดยตรง เว้นแต่ identity นั้นได้รับอนุมัติให้เป็น canonical ระยะยาว

---

## 3. Memory Type คืออะไร

`memory_type` ระบุชนิดหรือความหมายของข้อมูล โดยไม่ขึ้นกับ subject

ตัวอย่าง:

```text
Subject: plant:monstera-bedroom
Memory Type: care_instruction
Title: การรดน้ำ
```

Subject เดียวกันมี Memory Types หลายแบบได้ เช่น:

```text
care_instruction
observation
maintenance_note
warning
schedule
```

Memory Type ไม่ควรใช้แทน subject และไม่ควรนำ title ไปสร้างเป็น type

---

## 4. Memory Types ที่แนะนำ

### ข้อเท็จจริงและคุณสมบัติ

```text
fact
identity_fact
attribute
relationship
measurement
configuration
```

### ความชอบและพฤติกรรม

```text
preference
dislike
favorite
habit
```

### คำแนะนำและขั้นตอน

```text
instruction
care_instruction
operating_instruction
maintenance_instruction
procedure
checklist_item
```

### หมายเหตุและการสังเกต

```text
note
device_note
location_note
maintenance_note
observation
```

### คำเตือนและข้อจำกัด

```text
warning
restriction
safety_note
compatibility_note
known_issue
```

### สถานที่จัดเก็บและคลัง

```text
storage_location
item_location
inventory_note
```

### ตารางและรอบเวลา

```text
schedule
maintenance_schedule
care_schedule
reminder_rule
```

### คำศัพท์และการตั้งชื่อ

```text
terminology
vocabulary_note
alias_note
naming_convention
```

Alias หรือ Vocabulary ที่ผู้ใช้ยืนยันควรเก็บใน durable metadata structures ของ Core เมื่อระบบรองรับ ไม่ควรสร้างเป็น Memory ซ้ำโดยไม่จำเป็น

### การตัดสินใจและการเปลี่ยนแปลง

```text
decision
decision_reason
change_note
exception
```

### ข้อมูลทดสอบ

```text
test_note
test_fact
test_instruction
```

ข้อมูลทดสอบควรใช้ร่วมกับ:

```text
scope = system_test
subject = test:<id>
```

---

## 5. Collection Type คืออะไร

`collection_type` ระบุชนิดของชุดข้อมูลที่ประกอบด้วยหลาย Sections ซึ่งใช้ subject และ scope เดียวกัน

ตัวอย่าง:

```text
Subject: plant:monstera-bedroom
Collection Type: care_guide
Title: คู่มือดูแลมอนสเตอร่า
```

Sections:

```text
1. ตำแหน่งและแสง
2. การรดน้ำ
3. การใส่ปุ๋ย
```

Collection Types ที่แนะนำ:

```text
guide
care_guide
operating_guide
maintenance_guide
troubleshooting_guide
reference
profile
inventory
checklist
procedure
policy
configuration_guide
preference_profile
location_guide
test_guide
```

ใช้ Collection เมื่อต้องการลำดับ การดูแลแยก Section หรือ assembled preview ไม่ควรใช้ Collection กับข้อเท็จจริงสั้นที่เข้าใจได้ด้วยตัวเอง

---

## 6. การสร้าง Subject ใหม่

สามารถสร้าง Subject เพิ่มได้เรื่อย ๆ โดยไม่ต้องแก้ schema หรือ migration เพราะ Subject เป็น canonical identity string

ก่อนสร้าง Subject ใหม่ ให้ตรวจ:

1. มี Subject เดิมที่หมายถึงสิ่งเดียวกันอยู่แล้วหรือไม่
2. ชื่อใหม่นี้ควรเป็น Alias ของ Subject เดิมหรือไม่
3. Domain สอดคล้องกับ Catalog ปัจจุบันหรือไม่
4. Canonical ID จะมีความหมายและเสถียรในระยะยาวหรือไม่
5. มีข้อมูลอ่อนไหวหรือ secret ปนอยู่หรือไม่

ตัวอย่างที่ถูกต้อง:

```text
Canonical Subject:
device:air-conditioner-bedroom

Aliases:
แอร์ห้องนอน
เครื่องปรับอากาศห้องนอน
แอร์ในห้องนอน
```

ไม่ควรสร้าง Subject แยกสามรายการสำหรับ Alias ทั้งสามคำ

---

## 7. การสร้าง Type ใหม่

สามารถสร้าง `memory_type` และ `collection_type` เพิ่มได้ หาก schema เก็บ Type เป็น string แต่ต้องควบคุมด้วย Catalog เพื่อหลีกเลี่ยงความหมายซ้ำ

Workflow ที่แนะนำ:

1. ตรวจ Type Catalog ปัจจุบัน
2. ถ้ามี Type ที่ความหมายตรงหรือใกล้เคียง ให้ใช้ของเดิม
3. ถ้าไม่มีจริง ให้เสนอ Type ใหม่
4. ใช้ `lowercase_snake_case`
5. เขียน definition และตัวอย่าง
6. เพิ่มในเอกสาร Type Catalog
7. เพิ่ม test หาก Type มีผลต่อ validation, behavior, ranking หรือ Resolver

ตัวอย่างที่ดี:

```text
care_instruction
maintenance_schedule
device_note
troubleshooting_step
```

ตัวอย่างที่ไม่ควรใช้:

```text
CareInstruction
care-instruction
คำแนะนำดูแล
type1
general
other
```

ควรหลีกเลี่ยง `general` และ `other` เพราะทำให้ความหมายของข้อมูลไม่ชัดเจน

---

## 8. Scope ที่แนะนำ

`scope` ระบุขอบเขตการใช้งานและการแยกข้อมูล

Catalog เริ่มต้น:

```text
personal
household
property
system
system_test
```

ความหมาย:

- `personal`: ความชอบหรือข้อมูลเฉพาะบุคคล
- `household`: ความรู้ที่สมาชิกในบ้านใช้ร่วมกัน
- `property`: ข้อมูลของบ้านหรือทรัพย์สินเฉพาะแห่ง
- `system`: configuration หรือความรู้ภายในระบบ
- `system_test`: ข้อมูลสังเคราะห์สำหรับ tests และ acceptance dataset

กฎ Collection:

```text
section.subject = collection.subject
section.scope = collection.scope
section.title = ชื่อหัวข้อย่อย
```

- Section ใหม่ inherit Subject และ Scope จาก Collection
- ย้าย Memory เดิมเข้า Collection ได้เฉพาะเมื่อ Subject และ Scope ตรงกัน
- Collection ที่มี Sections แล้วห้ามเปลี่ยน Subject หรือ Scope โดยตรง

---

## 9. Catalog เริ่มต้นที่แนะนำ

### Subject Domains

```text
person
household
location
device
equipment
plant
pet
music
playlist
routine
activity
inventory
item
supply
service
system
integration
automation
topic
policy
project
test
```

### Memory Types

```text
fact
attribute
relationship
configuration
preference
habit
instruction
care_instruction
operating_instruction
maintenance_instruction
procedure
note
device_note
location_note
maintenance_note
observation
warning
restriction
safety_note
storage_location
inventory_note
schedule
maintenance_schedule
decision
change_note
known_issue
test_note
```

### Collection Types

```text
guide
care_guide
operating_guide
maintenance_guide
troubleshooting_guide
reference
profile
inventory
checklist
procedure
policy
configuration_guide
preference_profile
location_guide
test_guide
```

Catalog นี้เป็น baseline ไม่ใช่ enum แบบปิด สามารถขยายได้ตาม governance ที่กำหนด

---

## 10. แนวทางสำหรับ Portal และ Resolver

Portal ควรมี:

- Dropdown สำหรับ Types ที่ใช้บ่อย
- ตัวเลือก Custom Type
- Validation รูปแบบ `lowercase_snake_case`
- Subject domain suggestions
- Duplicate Subject warning
- Alias suggestion เมื่อชื่อใกล้กับ Subject เดิม
- คำอธิบาย Type ใต้ช่องเลือก
- ซ่อน technical identifier ที่ไม่จำเป็น แต่ยังแสดงใน Details สำหรับ debug

ไม่ควรทำ Type เป็น enum แบบปิดในฐานข้อมูล เพราะการเพิ่ม Type ใหม่จะต้อง migration ทุกครั้ง

Resolver ควร:

- ใช้ canonical Subject และ Type จาก Core โดยไม่ rewrite
- Normalize Alias และ Vocabulary เพื่อค้นหา
- รวม Alias หลายคำให้ชี้ไป Subject เดียว
- ไม่คืน Draft, Superseded, Forgotten หรือ Purged เป็นผลปกติ
- ใช้ Collection Subject และ Scope ร่วมกับ Sections
- ใช้ Section Title สำหรับค้นหัวข้อย่อย
- ใช้ `sequence_number ASC` สำหรับบริบทตามลำดับ

---

## สรุปหลักการ

```text
Subject:
เพิ่มได้เรื่อย ๆ แต่ต้อง canonical, namespaced, stable และไม่ซ้ำกับ Alias

Memory Type:
เพิ่มได้ แต่ต้องควบคุมด้วย documented catalog

Collection Type:
เพิ่มได้ เมื่อข้อมูลเป็นชุดหลาย Sections จริง

Scope:
ต้องสอดคล้องกับความหมายและสิทธิ์การใช้งาน

Schema:
ไม่ต้องเปลี่ยนเมื่อเพิ่ม Subject หรือ Type ใหม่

Resolver:
ใช้ Alias/Vocabulary เพื่อค้นหา แต่ไม่เปลี่ยน canonical identity ของ Core
```
