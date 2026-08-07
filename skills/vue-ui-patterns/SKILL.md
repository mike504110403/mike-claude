---
name: vue-ui-patterns
description: 現代 Vue 3 UI 模式，用於載入狀態、錯誤處理和資料獲取。在建構 UI 元件、處理異步資料或管理 UI 狀態時使用。
---

# Vue UI 模式

## 核心原則

1. **永不顯示過時的 UI** - 只在真正載入時顯示載入動畫
2. **總是顯示錯誤** - 使用者必須知道何時發生錯誤
3. **樂觀更新** - 讓 UI 感覺即時
4. **漸進式揭露** - 當內容可用時立即顯示
5. **優雅降級** - 部分資料勝過沒有資料

## 載入狀態模式

### 黃金法則

**只有在沒有資料可顯示時才顯示載入指示器。**

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'

const data = ref<Item[]>()
const loading = ref(false)
const error = ref<Error>()

const fetchItems = async () => {
  loading.value = true
  try {
    const response = await api.getItems()
    data.value = response.data
  } catch (e) {
    error.value = e as Error
  } finally {
    loading.value = false
  }
}

onMounted(fetchItems)
</script>

<template>
  <!-- 正確 - 按優先級檢查狀態 -->
  <ErrorState v-if="error" :error="error" @retry="fetchItems" />
  <LoadingState v-else-if="loading && !data" />
  <EmptyState v-else-if="!data?.length" />
  <ItemList v-else :items="data" />
</template>
```

```vue
<!-- 錯誤 - 即使有快取資料也顯示載入動畫 -->
<template>
  <LoadingState v-if="loading" /> <!-- 重新獲取時會閃爍！ -->
</template>
```

### 載入狀態決策樹

```
有錯誤嗎？
  → 是：顯示錯誤狀態，提供重試選項
  → 否：繼續

正在載入且沒有資料？
  → 是：顯示載入指示器（轉圈/骨架屏）
  → 否：繼續

有資料嗎？
  → 是，有項目：顯示資料
  → 是，但為空：顯示空狀態
  → 否：顯示載入（後備）
```

### 骨架屏 vs 載入動畫

| 使用骨架屏的時機 | 使用載入動畫的時機 |
|-------------------|------------------|
| 已知內容形狀 | 未知內容形狀 |
| 列表/卡片佈局 | 模態框操作 |
| 初始頁面載入 | 按鈕提交 |
| 內容佔位符 | 內聯操作 |

## 錯誤處理模式

### 錯誤處理層級

```
1. 內聯錯誤（欄位級別）→ 表單驗證錯誤
2. Toast 通知 → 可恢復的錯誤，使用者可重試
3. 錯誤橫幅 → 頁面級錯誤，資料仍部分可用
4. 全螢幕錯誤 → 無法恢復，需要使用者操作
```

### 總是顯示錯誤

**關鍵：永不靜默吞下錯誤。**

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

const loading = ref(false)

const createItem = async (data: CreateItemInput) => {
  loading.value = true
  try {
    await api.createItem(data)
    ElMessage.success('項目建立成功')
  } catch (error) {
    console.error('createItem failed:', error)
    ElMessage.error('建立項目失敗')
  } finally {
    loading.value = false
  }
}
</script>
```

```typescript
// 錯誤 - 靜默捕獲錯誤，使用者不知道
try {
  await api.createItem(data)
} catch (error) {
  console.error(error) // 使用者看不到任何提示！
}
```

### 錯誤狀態元件模式

```vue
<!-- ErrorState.vue -->
<script setup lang="ts">
interface Props {
  error: Error
  title?: string
}

const props = withDefaults(defineProps<Props>(), {
  title: '發生錯誤'
})

const emit = defineEmits<{
  retry: []
}>()
</script>

<template>
  <div class="error-state">
    <el-icon><CircleClose /></el-icon>
    <h3>{{ title }}</h3>
    <p>{{ error.message }}</p>
    <el-button @click="emit('retry')">重試</el-button>
  </div>
</template>
```

## 按鈕狀態模式

### 按鈕載入狀態

```vue
<template>
  <el-button
    type="primary"
    :loading="isSubmitting"
    :disabled="!isValid || isSubmitting"
    @click="handleSubmit"
  >
    提交
  </el-button>
</template>
```

### 操作期間禁用

**關鍵：在異步操作期間始終禁用觸發器。**

```vue
<!-- 正確 - 載入時禁用按鈕 -->
<template>
  <el-button
    :disabled="isSubmitting"
    :loading="isSubmitting"
    @click="handleSubmit"
  >
    提交
  </el-button>
</template>

<!-- 錯誤 - 使用者可以多次點擊 -->
<template>
  <el-button @click="handleSubmit">
    {{ isSubmitting ? '提交中...' : '提交' }}
  </el-button>
</template>
```

## 空狀態

### 空狀態要求

每個列表/集合都必須有空狀態：

```vue
<!-- 錯誤 - 沒有空狀態 -->
<template>
  <div v-for="item in items" :key="item.id">
    {{ item.name }}
  </div>
</template>

<!-- 正確 - 顯式空狀態 -->
<template>
  <div v-if="items.length">
    <div v-for="item in items" :key="item.id">
      {{ item.name }}
    </div>
  </div>
  <EmptyState v-else />
</template>
```

### 情境化空狀態

```vue
<!-- 搜尋無結果 -->
<EmptyState
  icon="search"
  title="未找到結果"
  description="嘗試不同的搜尋詞"
/>

<!-- 列表尚無項目 -->
<EmptyState
  icon="plus"
  title="尚無項目"
  description="建立您的第一個項目"
>
  <el-button type="primary" @click="handleCreate">
    建立項目
  </el-button>
</EmptyState>
```

## 表單提交模式

```vue
<script setup lang="ts">
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

const formRef = ref<FormInstance>()
const loading = ref(false)
const formData = reactive({
  name: '',
  email: ''
})

const rules: FormRules = {
  name: [{ required: true, message: '請輸入姓名', trigger: 'blur' }],
  email: [
    { required: true, message: '請輸入郵箱', trigger: 'blur' },
    { type: 'email', message: '請輸入有效的郵箱', trigger: 'blur' }
  ]
}

const handleSubmit = async () => {
  if (!formRef.value) return
  
  await formRef.value.validate(async (valid) => {
    if (!valid) {
      ElMessage.error('請修正錯誤')
      return
    }
    
    loading.value = true
    try {
      await api.submit(formData)
      ElMessage.success('提交成功')
    } catch (error) {
      console.error('submit failed:', error)
      ElMessage.error('提交失敗')
    } finally {
      loading.value = false
    }
  })
}
</script>

<template>
  <el-form ref="formRef" :model="formData" :rules="rules">
    <el-form-item label="姓名" prop="name">
      <el-input v-model="formData.name" />
    </el-form-item>
    
    <el-form-item label="郵箱" prop="email">
      <el-input v-model="formData.email" type="email" />
    </el-form-item>
    
    <el-form-item>
      <el-button
        type="primary"
        :loading="loading"
        :disabled="loading"
        @click="handleSubmit"
      >
        提交
      </el-button>
    </el-form-item>
  </el-form>
</template>
```

## 反模式

### 載入狀態

```vue
<!-- 錯誤 - 當資料存在時顯示載入動畫（導致閃爍） -->
<template>
  <LoadingState v-if="loading" />
</template>

<!-- 正確 - 只在沒有資料時顯示載入 -->
<template>
  <LoadingState v-if="loading && !data" />
</template>
```

### 錯誤處理

```typescript
// 錯誤 - 吞下錯誤
try {
  await mutation()
} catch (e) {
  console.log(e) // 使用者不知道！
}

// 正確 - 顯示錯誤
try {
  await mutation()
} catch (error) {
  console.error('operation failed:', error)
  ElMessage.error('操作失敗')
}
```

### 按鈕狀態

```vue
<!-- 錯誤 - 提交期間按鈕未禁用 -->
<template>
  <el-button @click="submit">提交</el-button>
</template>

<!-- 正確 - 禁用並顯示載入 -->
<template>
  <el-button :disabled="loading" :loading="loading" @click="submit">
    提交
  </el-button>
</template>
```

## 檢查清單

完成任何 UI 元件前：

**UI 狀態：**
- [ ] 錯誤狀態已處理並向使用者顯示
- [ ] 載入狀態僅在沒有資料時顯示
- [ ] 為集合提供空狀態
- [ ] 異步操作期間禁用按鈕
- [ ] 適當時按鈕顯示載入指示器

**資料與操作：**
- [ ] API 調用有錯誤處理
- [ ] 所有使用者操作都有回饋（toast/視覺）

## 與其他技能的整合

- **vue-form-patterns**: 使用表單提交模式
- **testing-patterns**: 測試所有 UI 狀態（載入、錯誤、空、成功）
- **systematic-debugging**: 系統性地除錯 UI 問題
