# Panokeet Karabiner Rules

Copy this JSON and paste into Karabiner → Complex Modifications → Add your own rule:

```json
{
  "description": "Panokeet: Cmd+Keypad7 → F13, Cmd+Keypad8 → F14",
  "manipulators": [
    {
      "type": "basic",
      "from": {
        "key_code": "keypad_7",
        "modifiers": {
          "mandatory": ["command"]
        }
      },
      "to": [
        {
          "key_code": "f13"
        }
      ]
    },
    {
      "type": "basic",
      "from": {
        "key_code": "keypad_8",
        "modifiers": {
          "mandatory": ["command"]
        }
      },
      "to": [
        {
          "key_code": "f14"
        }
      ]
    }
  ]
}
```
